# 기술 결정 로그

> 이 문서는 중요한 기술 판단과 그 근거를 정리한 문서입니다. 상세한 handoff는 `CONTEXT.md`, 다음 실험은 `PLAN.md`를 참고합니다.

---

## 핵심 결정 요약

### 1. DART XML을 직접 해석하는 구조 기반 parser를 채택

문제:

- DART 문서는 일반 HTML 전제가 아니라 `SECTION-*`, `TABLE-GROUP` 같은 비표준 구조를 가진다.

결정:

- 범용 split보다 DART 구조를 직접 읽는 parser를 구축한다.

결과:

- 섹션, 문단, 표 경계를 보존한 청킹이 가능해졌고
- retrieval, citation, parent-child 확장의 기반이 됐다.

### 2. 한국어 공시에 맞는 retrieval 스택으로 재설계

문제:

- 초기 retrieval은 한국어 공시에서 기업/연도/주제 구분력이 약했고 contamination이 발생했다.

결정:

- 임베딩을 `paraphrase-multilingual-MiniLM-L12-v2`로 교체
- BM25를 character bigram 기반으로 조정
- dedup 기준을 `chunk_uid`로 변경
- metadata filter를 non-empty 유지 방식으로 수정

결과:

- single-company 질의의 wrong-document contamination을 구조적으로 줄였다.

### 3. parent-child + contextual retrieval 채택

문제:

- 작은 chunk는 검색에는 유리하지만 답변에 필요한 문맥이 부족했다.

결정:

- 검색은 자식 chunk로 수행
- 답변은 부모 섹션 텍스트를 우선 사용
- 인덱싱 시 LLM context를 prepend

결과:

- retrieval granularity와 reasoning context를 분리한 구조를 만들었다.

### 4. evidence-first reasoning 채택

문제:

- retrieved context 전체를 바로 요약하면 근거가 약한 정보도 답변에 섞일 수 있었다.

결정:

- `retrieve -> evidence -> analyze -> cite` 흐름으로 재구성한다.

결과:

- 답변과 근거의 연결이 명확해졌고
- 근거 부족이나 충돌을 답변에 드러낼 수 있게 됐다.

### 5. 평가를 retrieval-aware로 확장

문제:

- faithfulness, relevancy, recall만으로는 retrieval 실패와 synthesis 실패를 분리하기 어려웠다.

결정:

- `retrieval_hit_at_k`, `section_match_rate`, `citation_coverage`를 추가한다.

결과:

- MLflow에서 retrieval 회귀와 answer 회귀를 따로 추적할 수 있게 됐다.

### 6. 성능 튜닝은 측정 기반으로 진행

문제:

- contextual ingest가 문서 하나 인덱싱에도 과도하게 오래 걸렸다.

결정:

- `llm.batch(..., max_concurrency=...)` 기반 병렬 처리 도입
- chunk size 후보를 비교 실험

결과:

- `1500 / 200`: `502` chunks, `1013.569초`
- `2800 / 350`: `266` chunks, `292.289초`, 하지만 리스크 질의 품질 회귀
- `2500 / 320`: `300` chunks, `584.25초`, 최종 채택

---

## 상세 결정

### 결정 1. `lxml XMLParser(recover=True)` 사용

배경:

- DART XML은 비표준 태그와 복구 가능한 오류를 포함한다.

결정:

- `lxml.etree.XMLParser(recover=True, huge_tree=True)`를 사용한다.

효과:

- 대용량 사업보고서도 안정적으로 파싱할 수 있게 됐다.

### 결정 2. 섹션 경계는 `SECTION-1/2/3` 기준으로 구성

배경:

- 공시 문서의 논리 섹션을 안정적으로 분리할 기준이 필요했다.

결정:

- `SECTION-1/2/3`과 `TITLE ATOC="Y"`를 기준으로 섹션을 구성한다.

효과:

- 문서 구조를 크게 훼손하지 않고 청킹할 수 있게 됐다.

### 결정 3. 청킹은 구조 우선, 문자 분할은 fallback

배경:

- 순수 문자 분할은 문단/표 경계를 무너뜨리고 작은 chunk를 과도하게 만든다.

결정:

- 먼저 구조 기반으로 블록을 묶고
- 너무 긴 블록만 문자 단위로 분할한다.

효과:

- 구조 보존과 retrieval 효율 사이의 균형을 잡았다.

### 결정 4. 작은 표는 문단과 함께, 큰 표는 standalone

배경:

- 모든 표를 단독 chunk로 두면 소형 참조 표가 너무 많이 쪼개졌다.

결정:

- threshold 미만 표는 문단과 함께 누적하고
- 큰 표만 standalone 처리한다.

효과:

- 표 검색성과 문맥 보존을 동시에 개선했다.

### 결정 5. BM25는 character bigram 기반

배경:

- 한국어 조사 결합형 때문에 공백 분리 토크나이징만으로는 lexical retrieval이 약했다.

결정:

- BM25에 character bigram 토크나이저를 사용한다.

효과:

- 한국어 재무 용어 검색 품질이 개선됐다.

### 결정 6. 임베딩 모델 교체와 컬렉션 분리

배경:

- 기존 영문 중심 임베딩은 한국어 공시 retrieval에 한계가 있었다.

결정:

- 다국어 임베딩으로 교체하고 컬렉션을 `dart_reports_v2`로 분리한다.

효과:

- 새 retrieval 기준을 분리해 실험과 운영을 명확히 나눌 수 있게 됐다.

### 결정 7. `chunk_uid` 기준 fusion

배경:

- raw `page_content` 기준 dedup은 boilerplate 반복 시 출처를 섞을 수 있었다.

결정:

- `chunk_uid`를 hybrid fusion과 dedup 기준으로 사용한다.

효과:

- repeated text 때문에 서로 다른 chunk가 합쳐지는 문제를 줄였다.

### 결정 8. strict metadata filtering 보강

배경:

- 필터 결과가 1개만 남아도 기존 로직은 broader candidate로 되돌아갔다.

결정:

- filter 결과가 non-empty면 그대로 유지한다.

효과:

- single-company contamination이 크게 줄었다.

### 결정 9. evidence-first reasoning 도입

배경:

- retrieve 직후 summarize 방식은 약한 근거를 과대 해석할 위험이 있었다.

결정:

- evidence bullet 추출 단계를 명시적으로 추가한다.

효과:

- 답변의 근거 추적 가능성이 좋아졌다.

### 결정 10. parent-child + contextual retrieval 도입

배경:

- 검색 정밀도와 답변용 문맥은 서로 다른 최적점을 가진다.

결정:

- child chunk 검색과 parent context 사용을 분리한다.
- child chunk 앞에 LLM context를 prepend한다.

효과:

- retrieval과 answer synthesis가 각각 더 안정적으로 동작하게 됐다.

### 결정 11. contextual ingest 병렬화

배경:

- child chunk 수만큼 LLM을 순차 호출하면 ingest가 지나치게 느리다.

결정:

- `llm.batch()` 기반 병렬 처리로 전환한다.

효과:

- 순차 방식 대비 ingest 처리량이 크게 개선됐다.

### 결정 12. chunk size 최적점은 속도와 품질을 함께 보고 선택

배경:

- chunk를 키우면 ingest는 빨라지지만 retrieval 품질이 흔들릴 수 있다.

결정:

- `1500 / 200`, `2800 / 350`, `2500 / 320`을 비교해
- 품질 회귀가 없는 선에서 최종 기본값을 선택한다.

효과:

- “가장 빠른 값”이 아니라 “가장 균형이 좋은 값”을 기본값으로 채택했다.

### 결정 13. 벤치마크 자동화 추가

배경:

- 수동 실험만으로는 설정 비교와 문서화가 반복 가능하지 않았다.

결정:

- `benchmark_runner.py`와 실험 설정 파일을 추가해
- 정확도, 속도, 비용을 같은 형식으로 기록한다.

효과:

- 이후의 tuning을 측정 기반으로 비교하고 문서화할 수 있게 됐다.

---

## 운영 메모

- Python 3.14에서 `langchain_core` 관련 경고가 남아 있음
- `langchain_community.vectorstores.Chroma` deprecation 경고가 있음
- Hugging Face cache는 `.gitignore`로 제외함
