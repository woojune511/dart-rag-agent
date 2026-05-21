# Presentation Outline

이 문서는 취업용 포트폴리오 발표나 면접 설명용으로 바로 쓸 수 있는 슬라이드 구조다.

## Slide 1. Title

- 프로젝트명
- 한 줄 요약
  - `Evidence-backed numeric QA over DART filings with multi-agent RAG and explicit calculation traces`

## Slide 2. Problem

- DART 공시는 길고 표 중심이며 숫자/기간/엔티티 바인딩이 어렵다
- 일반 RAG failure mode:
  - wrong row
  - wrong subtotal
  - wrong entity
  - wrong period
  - numeric equivalence mismatch

## Slide 3. Goal

- 단순 QA 챗봇이 아니라:
  - 근거가 있는 답변
  - 계산 trace
  - 평가 가능한 결과
  를 만드는 시스템

## Slide 4. System Architecture

- Orchestrator / Analyst / Researcher / Critic
- shared contracts:
  - `answer_slots`
  - `structured_result`
  - `resolved_calculation_trace`

## Slide 5. Key Design Choices

- concept-first planner
- direct-first grounding
- deterministic calculator
- evaluator split

이 슬라이드는 “왜 이런 분해가 필요했는가”를 강조해야 한다.

## Slide 6. Retrieval / Ingest Strategy

- `plain_prefix_8000_400`
- `structural_selective_v2_prefix_2500_320`
- `contextual_selective_v2_prefix_2500_320`

보여줄 메시지:
- plain은 싸지만 약함
- contextual은 강하지만 비쌈
- structural은 중간 후보

## Slide 7. Benchmark Strategy

- `runtime_contract_gate`
  - 5문항
- `multi_entity_grounding_gate`
  - 3문항

이 슬라이드는 “내가 무엇을 official gate로 삼았는가”를 보여준다.

## Slide 8. Quantitative Results

권장 표:

| candidate | runtime gate | multi-entity gate | ingest cost/time |
| --- | --- | --- | --- |
| plain | one fail | not default | lowest |
| structural | pass | pass | much lower than contextual |
| contextual | pass | pass | highest |

핵심 메시지:
- structural selective가 현재 운영 기본값 후보

## Slide 9. Failure Analysis

2~3개만 고른다.

- `NAV_T1_071`
  - current/prior binding
- `SKH_T1_060`
  - wrong numerator row / subtotal
- `KBF_T1_017`
  - percent metric + period binding

각 케이스에 대해:
- original failure
- cause
- fix
- after result

## Slide 10. What this demonstrates

- long-form financial RAG failure mode analysis
- LLM/deterministic boundary design
- benchmark-driven iteration
- quality/cost tradeoff engineering

## Slide 11. Future Work

- `tasks + artifacts`를 source of truth로 더 강화
- additional chunking/index experiments
  - structural parent hybrid
  - adaptive block selective
  - table-first dual index
- curated benchmark coverage 확장

## Slide 12. Closing

- 문제를 어떻게 정의했는지
- 어떤 설계 선택을 했는지
- 어떤 근거로 검증했는지

이 세 줄만 다시 강조하고 끝낸다.

