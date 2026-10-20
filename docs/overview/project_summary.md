# Project Summary

DART 공시의 표와 본문을 위한 구조 보존형 RAG입니다. 직접 구축·검수한
11개 기업·77문항 데이터셋과 검색·답변 실패 분석을 함께 공개합니다.

[프로젝트 홈](../../README.md) · [아키텍처](project_overview.md) ·
[평가 결과와 한계](../evaluation/README.md) · [데모](simple_rag_demo.md)

## 구현

- 절 제목, 표의 행·열·단위, 공시 ID를 보존하는 파서와 ingest.
- 같은 명시적 보고서 범위를 적용하는 Chroma dense/BM25 검색과 RRF 결합.
- 검색 1회·답변 생성 최대 1회인 `SimpleRagAgent`, 응답 형식·출처 ID 검사,
  인용 원문·보류·검증 한계를 제공하는 FastAPI/Streamlit.
- 수치 22개·요약/혼합 36개·거절 19개의 QA 데이터셋, 원문 대조 평가와
  호출·토큰·비용·시간 기록, 검색 누락과 해석 오류의 구분.

## 공개된 결과

2026-09-28 전체 평가에서 **77/77 실행 완료**, 답변 가능 문항 **30/55 통과**,
거절 문항 **18/19 통과**였습니다. 처음 제외한 기준 충돌 3개 외에 후속 검토에서
1개를 더 확인했으며, 이를 제외하면 30/54입니다. 정확성·요청 충족·인용 근거가
모두 만족되어야 통과합니다. [전체 보고서](../evaluation/simple_rag_full77_result.md)

별도 12문항 paired 비교의 답변형 결과는 hybrid 9/9, dense-only 5/9입니다.
별도 77문항 구조 비교에서는 일반 텍스트가 문서·표 구조 조건보다 전체 통과가
높았습니다. 이 결과들을 합산하거나 구조 보존의 일반적 우위로 표현하지 않습니다.
[실험별 조건](../evaluation/README.md)

모두 개발에 노출된 자체 데이터셋의 assistant 원문 대조 결과입니다. 독립 사람
평가나 미노출 회사의 일반화 성능은 측정하지 않았습니다. 출처 검사와 사후 검토는
별개이며, 앱은 산술·의미·요청 완전성을 자동 검증하지 않습니다.

## English summary

A document QA application for Korean DART filings, with structure-preserving
ingest, scoped Chroma/BM25 hybrid retrieval and inspectable citations.
The default SimpleRagAgent performs one search and at most one answer-generation
call, then checks response shape and source IDs. FastAPI and Streamlit share
the same service path.

A self-curated dataset covers 77 questions across 11 companies. The September 28
run completed all 77 questions: 30/55 answerable cases and 18/19 refusal cases
passed assistant source review. A later reference-conflict exclusion gives
30/54 answerable cases. These development-exposed results are not independent
human evaluation or unseen-company accuracy. Arithmetic, semantic support and
request completeness are not automatically validated by the application.
