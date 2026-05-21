# README Blueprint For Portfolio Use

이 문서는 현재 저장소의 README를 포트폴리오 제출용으로 다시 정리할 때 권장하는 목차를 적는다.

## Recommended README structure

1. **One-line summary**
   - 예:
     - `Evidence-backed numeric QA over DART filings with multi-agent RAG, explicit calculation traces, and benchmark gates.`

2. **Problem**
   - 왜 일반 RAG가 DART 재무 질문에서 실패하는가
   - wrong row / wrong subtotal / period binding / entity collapse / numeric equivalence 문제

3. **What I built**
   - system diagram
   - agent roles
   - runtime contracts
   - retrieval / grounding / calculation split

4. **Key design decisions**
   - concept-first planner
   - direct-first grounding
   - `answer_slots` / `structured_result` / `resolved_calculation_trace`
   - ingest candidate comparison

5. **Evaluation**
   - official gates
   - representative canaries
   - candidate comparison table
   - current winner and why

6. **Results**
   - runtime contract gate PASS summary
   - multi-entity gate PASS summary
   - cost/latency tradeoff summary

7. **Repository map**
   - `src/agent`
   - `src/ops`
   - `benchmarks/profiles`
   - `docs/architecture`
   - `docs/evaluation`

8. **How to reproduce**
   - setup
   - run app
   - run official gates

9. **What I learned**
   - LLM semantic planning vs deterministic execution
   - benchmark-first iteration
   - quality/cost tradeoff

## Suggested README section outline

```text
# Project name

## Summary
## Problem
## System Design
## Key Engineering Decisions
## Evaluation and Results
## Reproducibility
## Repository Guide
## Lessons Learned
```

## What to avoid

- tool list만 길게 쓰는 것
- “LangGraph, Chroma, Gemini를 썼다” 수준의 기술 나열
- benchmark 없이 “정확도가 좋아졌다”고 쓰는 것
- 실패 사례 없이 성공 사례만 쓰는 것

## What to emphasize

- 어떤 failure mode를 직접 정의했는가
- 왜 planner / grounding / evaluator를 분리했는가
- 어떤 gate로 설계를 검증했는가
- 어떤 candidate가 품질 baseline이고 어떤 candidate가 운영 후보인가

