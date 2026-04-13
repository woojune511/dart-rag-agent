# DART 기반 기업 공시 분석 AI Agent — 다음 로드맵

이 문서는 초기 구현 계획서가 아니라, 현재 구현 완료 상태를 기준으로 한 **다음 확장 로드맵**입니다.

---

## 현재 베이스라인

이미 구현된 범위:

- DART API 기반 문서 수집
- DART XML 파싱 및 구조 기반 청킹
- ChromaDB + BM25 + RRF 하이브리드 검색
- LangGraph 기반 재무 분석 에이전트
- FastAPI + Streamlit 인터페이스
- MLflow 기반 평가 파이프라인
- 단일 기업 질의 정확도 향상 스프린트

현재 기본 검색/에이전트 흐름:

```text
classify → extract → retrieve → evidence → analyze → cite
```

---

## 로드맵 원칙

- 기존 FastAPI / Streamlit 계약은 최대한 유지
- 큰 재작성보다 정확도와 확장성을 높이는 방향 우선
- 문서 수집량보다 검색 정밀도와 근거 품질을 먼저 안정화
- 기능 추가는 평가 지표로 회귀를 확인할 수 있어야 함

---

## Track 1 — Retrieval 고도화

### 목표

단일 기업 질의 정확도를 안정화하고, 멀티 기업/멀티 연도 질의에도 검색 오염이 적은 상태로 확장합니다.

### 후보 작업

1. rerank 로직을 rule-based에서 learned reranker 또는 cross-encoder 단계로 확장
2. 섹션별 prior를 더 세밀하게 조정
3. 연도 범위 질의에서 가까운 연도 우선 랭킹 정책 추가
4. 비교 질의 시 기업별 retrieval 균형화
5. retrieval failure case를 자동 수집해 regression set로 축적

### 성공 기준

- known wrong-document contamination 재발 없음
- retrieval_hit_at_k와 section_match_rate가 현재 베이스라인보다 개선

---

## Track 2 — Chunking / Table 이해 강화

### 목표

재무 문서에서 숫자 질의와 표 기반 질의의 정확도를 높입니다.

### 후보 작업

1. 표 헤더 계층을 더 구조적으로 보존
2. 수치 질의용 normalized numeric metadata 추가
3. 연결/별도 재무제표 구분 메타데이터 추가
4. 표 split 시 열 헤더 반복 전략 개선
5. 핵심 재무표 전용 parser branch 도입 검토

### 성공 기준

- 매출액, 영업이익, CAPEX, R&D 비용 같은 숫자 질의에서 citation coverage 유지
- 표가 길어도 계정명과 값이 다른 청크로 흩어지는 현상 감소

---

## Track 3 — Reasoning 고도화

### 목표

근거 추출은 유지하되, 답변이 더 명시적이고 검증 가능하게 만듭니다.

### 후보 작업

1. evidence bullet에 claim type 태그 추가
2. 충돌 증거 탐지 로직을 더 명확히 분리
3. 질의 유형별 answer schema 고정
4. "문서에 없음" 응답 패턴 강화
5. 숫자 비교 / 시계열 분석 전용 synthesis prompt 분기

### 성공 기준

- 답변이 불확실성을 숨기지 않음
- 잘못된 단정 표현 감소
- faithfulness가 유지되거나 상승

---

## Track 4 — Evaluation / Ops

### 목표

모델, 청킹, 검색 정책을 바꿔도 회귀를 빠르게 탐지할 수 있게 합니다.

### 후보 작업

1. 단일 기업 평가셋을 실제 공시 기준으로 더 정교화
2. 멀티 기업 비교 평가셋 추가
3. MLflow 비교 리포트 자동화
4. synthetic regression 사례를 fixture화
5. CI에서 lightweight smoke eval 실행 검토

### 성공 기준

- retrieval / answer 양쪽 지표를 함께 추적
- 변경 후 품질 악화를 빠르게 탐지 가능

---

## Track 5 — Product / System 확장

### 목표

현재의 단일 질문-응답 데모를 더 실무형 분석 도구로 확장합니다.

### 후보 작업

1. 멀티턴 대화 메모리
2. 기업 watchlist 기반 주기적 수집
3. 질의 결과 export
4. 인덱싱 상태 및 컬렉션 관리 UI
5. 배치 재인덱싱 및 운영용 health check 강화

### 성공 기준

- 데모 성격을 넘어 반복 사용 가능한 분석 도구로 발전
- 운영 상태와 데이터 최신성을 확인하기 쉬움

---

## 추천 다음 스프린트

가장 우선 추천하는 순서:

1. `dart_reports_v2`로 실제 기업 데이터 재인덱싱
2. 단일 기업 숫자 질의와 리스크 질의를 end-to-end 검증
3. 평가셋에 retrieval regression 사례 반영
4. 표 기반 숫자 질의 개선 작업 착수

---

## 참고 문서

- `README.md`: 현재 사용법과 구조
- `CONTEXT.md`: 다음 세션 인수인계 정보
- `DECISIONS.md`: 기술 결정 및 버그 해결 로그
- `REVIEW_FINDINGS.md`: 최근 코드 리뷰 findings
