# Project Summary

현재 기본 제품인 `SimpleRagAgent`와 2026-09-22 최종 앱 평가,
2026-09-28 vanilla dense baseline 및 표 검색 2×2 비교를 기준으로 작성했다.
수치는 이미 개발에 노출된 공시와 문항의 결과이며, 독립 holdout이나 일반
정확도로 표현하지 않는다. 기존 답변 품질12문항과 별도 표 중심8+1문항 결과를 섞지 않는다.

## 구현 요약

### 핵심 기능과 비교 결과

한국 DART 공시를 위한 구조 보존형 RAG를 개발하고, 동일 LLM·prompt·top-k의
vanilla dense baseline과 비교해 hybrid BM25·vector RRF의 완전 근거 검색과
원문 지지 답변을 5/9에서 9/9로 개선했다.

### 주요 구현

- DART 공시의 절·표·행/열·단위·문서 ID를 보존하는 ingest와 명시적 보고서
  범위가 적용된 Chroma dense/BM25 hybrid retrieval을 구현했다.
- 기본 실행 경로를 검색 1회와 구조화 답변 생성 최대 1회로 단순화하고,
  범위 누출·출처 ID·응답 schema를 fail-closed로 검사하며 검증하지 않는
  산술·의미·요청 누락을 응답에 명시했다.
- 개발 노출 12문항의 paired evaluation에서 hybrid가 dense-only 대비 답변
  가능한 문항의 완전·정확·원문 지지 응답을 5/9에서 9/9로 높였고, 호출 수·
  토큰·비용 상한·무재시도·원본 hash를 기록하는 평가 harness를 구축했다.

### 비용과 실험에 따른 설계 판단

- Planner/Compiler 경로와 Simple RAG를 고정 근거 4문항에서 비교해 복잡한
  경로가 3.47배 추정 비용과 4.79배 측정 시간을 사용하면서 명확한 품질
  우위를 보이지 않음을 확인하고, Simple RAG를 기본 제품으로 채택했다.
- 후속 12문항 앱 평가와 dense-only baseline은 질문·rubric·모델·prompt·
  schema·예산을 사전 고정하고 단 한 번 실행했다. 실패·기권·NOT_RUN을
  분리하고 raw request/response를 SHA-256으로 동결했다.

### 표 구조 비교

- 표 중심 문항에서 flat/structured × dense/RRF 2×2 ablation을 설계해
  표현 방식과 fusion 효과를 분리했다. 정답 원문 검토에서 은행·그룹을
  혼동한 평가 기준을 발견해 진단 문항으로 분리하고, 검색 anchor 일치와
  실제 정답·인용 지지를 구분해36개 답변을 평가했다. Structured+RRF4/8,
  flat+RRF5/8로 전체 우위가 없음을 확인하고, 특정 표 경계 복원이 정답으로
  이어진 사례와 기간·계산·설명 누락 실패를 함께 분석했다.

## English version

Built a structure-preserving RAG application for Korean DART filings with
explicit report scoping, hybrid Chroma/BM25 retrieval, inspectable citations and
fail-closed source-ID validation. In a paired, development-exposed 12-question
evaluation using the same answer model, prompt and top-k, hybrid retrieval
increased fully correct, complete and source-supported positive answers from
5/9 for a dense-only baseline to 9/9. Designed a one-shot evaluation harness
with frozen inputs, zero retries, provider-cost caps and immutable raw receipts.

## 결과의 한계

- 비교 문항과 NAVER 두 공시는 개발 과정에 노출됐다.
- Dense arm은 저장된 query vector를 replay했으므로 live retrieval 지연시간
  비교가 아니다.
- Simple RAG는 출처 ID와 범위를 검사하지만 산술을 코드로 실행하지 않고,
  각 문장의 의미 지지나 요청 항목 완전성을 자동 판정하지 않는다.
- 9/9 대 5/9는 이 고정 패널의 관측치이지 새로운 회사나 전체 DART 질의의
  정확도 추정치가 아니다.

## 피해야 할 표현

- “금융 TableQA SOTA 달성”
- “환각 제거” 또는 “모든 답변의 의미 정확성 검증”
- “프로덕션 규모 배포”
- “독립 holdout에서 정확도 100%”
- “dense보다 hybrid가 항상 우수”

상세 근거는 [최종 앱 평가](../evaluation/simple_rag_final_result.md),
[vanilla dense 비교](../evaluation/vanilla_dense_comparison.md),
[표 검색 2×2 비교](../evaluation/structure_retrieval_factorial.md),
[표 답변 2×2 비교](../evaluation/structure_answer_result.md),
[제품 소개](project_overview.md)에서 확인한다.
