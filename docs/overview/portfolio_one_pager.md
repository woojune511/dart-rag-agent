# Portfolio One-Pager

## Project

**DART Multi-Agent Financial Analysis Lab**

장문 한국어 재무 공시에서 **근거가 있는 숫자 답변**을 생성하는 LLM agent / RAG 시스템을 설계하고 검증한 프로젝트다.

## Problem

일반적인 RAG는 DART 사업보고서 같은 문서에서 아래 문제를 자주 일으킨다.

- 표와 문단이 섞인 장문 문서에서 wrong row / wrong subtotal을 고른다
- `2023 값`, `2022 값`, `증감` 같은 period binding이 흔들린다
- `DX`, `DS`, `SDC`, `Harman` 같은 entity/segment 구분이 company-total row로 붕괴한다
- 계산형 질문에서 retrieval은 맞아도 rendering과 evaluator가 동치성을 놓친다

이 프로젝트의 목표는 “그럴듯한 답변”이 아니라 다음을 동시에 만족하는 시스템을 만드는 것이다.

- evidence-backed retrieval
- explicit calculation trace
- numeric grounding
- reproducible benchmark gate

## Approach

### 1. Agent / runtime contract

- query interpretation은 LLM이 맡고, retrieval / grounding / calculation은 deterministic code가 맡는다
- runtime 결과는 flat text가 아니라 아래 structured contract로 남긴다
  - `answer_slots`
  - `structured_result`
  - `resolved_calculation_trace`
- planner는 metric recipe보다 concept-first material gathering 쪽으로 정리했다

### 2. Numeric grounding architecture

- direct-first grounding
  - direct row/value가 있으면 재구성보다 먼저 채택
- pair-aware reconciliation
  - current/prior를 독립적으로 고르지 않고 coherent pair로 선택
- symbolic calculation
  - `ratio`, `difference`, `growth`, `subtract`를 planner/executor로 분리
- evaluator split
  - `numeric_equivalence`
  - `numeric_grounding`
  - `numeric_retrieval_support`
  - `numeric_final_judgement`

### 3. Retrieval / ingest tradeoff

세 가지 ingest 전략을 비교했다.

- `plain_prefix_8000_400`
  - 가장 빠르고 싸지만 gate 하나를 놓침
- `contextual_selective_v2_prefix_2500_320`
  - 품질 baseline, ingest 비용이 큼
- `structural_selective_v2_prefix_2500_320`
  - selective filtering + deterministic structural prefix
  - Gemini contextual chunk summary 비용 없이 품질을 유지하는 중간 후보

## Design Choices

### Why concept-first planning

질문마다 metric family를 늘리는 방식은 확장성이 낮았다.  
그래서 planner는 질문을 `lookup`, `ratio`, `difference`, `sum`, `growth_rate`와 ontology concept 조합으로 분해하게 바꿨다.

### Why structured runtime contract

`calculation_result` 같은 flat payload는 renderer, evaluator, benchmark export 사이에서 drift가 생기기 쉬웠다.  
그래서 `answer_slots`와 `resolved_calculation_trace`를 public/runtime contract로 올리고, legacy projection을 제거했다.

### Why direct-first grounding

재무 질문의 품질 문제는 retrieval miss보다 **wrong row acceptance**에 가까운 경우가 많았다.  
그래서 candidate scoring만이 아니라 acceptance contract를 두어 surrogate metric, wrong subtotal, wrong entity row를 reject하도록 바꿨다.

## Evaluation

### Official gates

- `runtime_contract_gate`
  - `NAV_T1_030`
  - `NAV_T1_071`
  - `MIX_T1_021`
  - `KBF_T1_017`
  - `SKH_T1_060`
- `multi_entity_grounding_gate`
  - `comparison_001`
  - `comparison_002`
  - `comparison_003`

### Current quantitative snapshot

#### Runtime contract gate

- `plain_prefix_8000_400`
  - `SKH_T1_060` FAIL
- `contextual_selective_v2_prefix_2500_320`
  - 대표 5문항 PASS
- `structural_selective_v2_prefix_2500_320`
  - 대표 5문항 PASS

#### Multi-entity grounding gate

- `contextual_selective_v2_prefix_2500_320`
  - 3문항 PASS
- `structural_selective_v2_prefix_2500_320`
  - 3문항 PASS

### Cost / latency tradeoff

runtime gate 결과 기준:

- `contextual_selective_v2_prefix_2500_320`
  - NAVER `1532s`
  - 삼성전자 `1170s`
  - KB금융 `3033s`
  - SK하이닉스 `1268s`
- `structural_selective_v2_prefix_2500_320`
  - NAVER `165s`
  - 삼성전자 `154s`
  - KB금융 `421s`
  - SK하이닉스 `79s`

즉 `structural_selective_v2`는 current gate 기준으로 **품질은 유지하면서 ingest 시간을 크게 줄인 후보**다.

## What this project demonstrates

- long-form financial RAG의 failure mode를 retrieval / grounding / calculation / evaluation으로 분해하는 능력
- LLM과 deterministic code의 역할 경계를 설계하는 능력
- benchmark-first, gate-driven iteration
- 품질과 비용을 동시에 보는 retrieval / ingest tradeoff engineering

## Recommended portfolio framing

이 프로젝트를 “공시 QA 챗봇”으로 소개하는 것은 약하다.  
더 좋은 framing은 아래다.

> 장문 재무 공시에서 evidence-backed numeric QA를 수행하는 multi-agent RAG 시스템을 설계하고, official gate로 품질/비용 tradeoff를 검증했다.

