# 기술 결정 로그

> 이 문서는 프로젝트에서 중요한 설계 판단과 그 근거를 정리한 기록이다. 현재 상태와 다음 작업은 각각 `CONTEXT.md`, `PLAN.md`를 참고한다.

---

## 핵심 결정 요약

### 1. DART XML 전용 구조 기반 parser를 유지한다

일반 HTML 분할기가 아니라 DART의 `SECTION-*`, `TITLE`, `P`, `TABLE`, `TABLE-GROUP` 구조를 직접 읽는 parser를 채택했다.

이 결정으로 문단, 표, 섹션 경계를 보존한 청킹이 가능해졌고, 이후 retrieval, citation, parent-child 확장의 기반이 됐다.

### 2. 한국어 공시에 맞춘 retrieval stack을 별도로 최적화한다

초기 범용 설정 대신 아래 구성을 기준선으로 삼았다.

- multilingual embedding: `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2`
- BM25 tokenizer: character bigram
- hybrid fusion key: `chunk_uid`
- metadata filter: non-empty strict filtering

이 조합은 single-company 질의에서 wrong-document contamination을 줄이는 데 가장 큰 효과를 냈다.

### 3. 검색과 답변 컨텍스트를 분리하는 parent-child retrieval을 채택한다

검색은 child chunk 단위로, 답변 컨텍스트는 parent section 단위로 구성한다. 여기에 contextual ingest를 더해 child chunk 앞에 설명용 context를 붙여 인덱싱한다.

이 구조는 retrieval granularity와 reasoning context의 요구가 다르다는 점을 반영한 것이다.

### 4. evidence-first reasoning을 유지한다

답변을 바로 생성하지 않고 `retrieve -> evidence -> analyze -> cite` 흐름을 거친다.

이 방식은 근거 없는 요약을 줄이고, 정보가 부족하거나 충돌할 때 이를 명시적으로 드러내는 데 유리하다.

### 5. 성능 튜닝은 측정 기반으로 진행한다

청크 크기와 contextual ingest 전략은 감이 아니라 실측으로 비교한다.

현재까지의 대표 비교:

- `1500 / 200`: `502` chunks, contextual ingest `774.632s`
- `2500 / 320`: `300` chunks, contextual ingest `558.723s`
- `2800 / 350`: 속도는 더 빨랐지만 retrieval 품질 회귀가 확인됨

현재 기본값은 `2500 / 320`이다. 가장 빠른 값이 아니라 품질 하한선을 넘기면서 비용과 시간을 줄인 균형점으로 채택했다.

### 6. 벤치마크는 2단계 구조로 운영한다

모든 후보를 비싼 full evaluation으로 보내지 않고, screening에서 저비용 후보를 먼저 거른 뒤 통과안만 정식 평가로 올린다.

현재 기준:

- 1차 screening: ingest 시간, API 호출 수, 토큰 수, `retrieval_hit_at_k`, `section_match_rate`, `citation_coverage`
- 2차 full eval: `faithfulness`, `answer_relevancy`, `context_recall` 추가

이 구조는 API 비용을 통제하면서도 품질 하한선을 엄격하게 유지하기 위한 결정이다.

### 7. 실험 결과 자산은 repo에 남기고, 로컬 상태만 무시한다

전역 `*.json` ignore는 제거했다. 대신 아래만 계속 무시한다.

- `benchmarks/experiment_matrix.local.json`
- `benchmarks/results/**/stores/`
- `mlflow.db`

질문셋, 평가셋, benchmark 결과 JSON은 추적 가능하게 유지한다.

---

## 상세 결정

### 결정 1. `lxml` 복구 파서를 사용한다

배경:

- DART XML은 비표준 구조와 복구 가능한 파싱 오류를 포함하는 경우가 있다.

결정:

- `lxml.etree.XMLParser(recover=True, huge_tree=True)`를 사용한다.

효과:

- 대형 사업보고서도 안정적으로 파싱할 수 있다.

### 결정 2. 섹션 경계는 `SECTION-1/2/3`와 `TITLE ATOC="Y"` 기준으로 잡는다

배경:

- 공시 문서에서 section boundary를 잘못 잡으면 retrieval과 citation이 동시에 흔들린다.

결정:

- `SECTION-1/2/3`를 우선 경계로 사용하고, `TITLE ATOC="Y"`를 섹션 제목으로 읽는다.

효과:

- 문서 구조와 실제 목차를 최대한 보존하는 청킹이 가능해졌다.

### 결정 3. 청킹은 구조 우선, 문자 분할은 fallback으로 둔다

배경:

- 순수 문자 분할은 문단과 표의 경계를 무너뜨리고 불필요하게 많은 chunk를 만든다.

결정:

- 먼저 구조 기반으로 paragraph와 table block을 묶고, 너무 긴 블록만 추가 분할한다.

효과:

- 구조 보존과 검색 효율의 균형을 유지한다.

### 결정 4. 작은 표는 문단과 합치고, 큰 표는 standalone으로 둔다

배경:

- 모든 표를 독립 chunk로 만들면 표 주변 설명이 분리되고 호출 수가 급증한다.

결정:

- threshold 미만 표는 인접 문단과 함께 처리하고, 큰 표만 standalone chunk로 둔다.

효과:

- 표 검색성과 주변 문맥 보존을 동시에 확보할 수 있다.

### 결정 5. hybrid fusion은 `chunk_uid` 기준으로 병합한다

배경:

- raw `page_content` 기준 dedup은 반복 boilerplate와 표 헤더 때문에 출처를 섞을 위험이 있었다.

결정:

- `chunk_uid`를 chunk의 stable identifier로 부여하고 fusion과 dedup의 기준으로 사용한다.

효과:

- 동일 본문 일부가 반복되더라도 서로 다른 chunk를 구분할 수 있게 됐다.

### 결정 6. metadata filtering은 non-empty strict filter로 유지한다

배경:

- filter 후 1개만 남았을 때 broader candidate로 되돌아가면서 다른 기업 문서가 섞이는 문제가 있었다.

결정:

- 회사, 연도, 섹션 filter 결과가 non-empty이면 그대로 사용한다.

효과:

- single-company retrieval contamination이 크게 줄었다.

### 결정 7. contextual ingest는 child chunk 전부에 적용하되, 대안 모드를 계속 실험한다

배경:

- `contextual_all`은 품질이 좋지만 시간이 오래 걸리고 API 비용이 크다.

결정:

- 현재 기본 baseline은 `contextual_all`
- 대안으로 `plain`, `contextual_parent_only`, `contextual_selective`를 benchmark 전용 모드로 유지

효과:

- production 기본 동작은 안정적으로 유지하면서 비용 절감 실험을 병행할 수 있다.

### 결정 8. screening 실험은 bounded parallelism으로 실행한다

배경:

- 실험 수가 늘어나면서 전체 benchmark 벽시계 시간이 과도하게 길어졌다.

결정:

- `screening.parallel_experiments`를 도입해 screening 실험만 제한된 병렬도로 실행한다.
- 기본값은 `2`로 둔다.

효과:

- 총 소요 시간을 줄이면서도 rate limit과 리소스 경쟁을 과도하게 키우지 않는다.

### 결정 9. 삼성전자 2024 사업보고서를 첫 benchmark 기준 문서로 사용한다

배경:

- 실제 문서 기반 실험 없이는 기본값 채택 근거가 약하다.

결정:

- 삼성전자 2024 사업보고서를 첫 기준 문서로 고정하고, local benchmark 자산을 repo에 남긴다.

현재 local benchmark 요약:

- `plain_2500_320`: 가장 저렴하지만 risk retrieval이 무너짐
- `contextual_parent_only_2500_320`: API 호출 수는 크게 줄었지만 numeric retrieval miss 발생
- `contextual_selective_2500_320`: 호출 수를 거의 못 줄였고 business overview miss 발생
- `contextual_all_2500_320`: screening 통과
- `contextual_1500_200`: 더 느리고 business overview miss 발생

효과:

- 이후 실험이 모두 같은 출발점과 비교 기준을 갖게 됐다.

### 결정 10. 기본 benchmark 운영 모드는 `Fast Iteration + Hybrid Cache`로 둔다

배경:

- 3기업 full benchmark를 한 번에 돌리면 1시간 timeout과 API 비용 낭비가 쉽게 발생한다.
- 반복 실험의 대부분은 “새 후보가 baseline보다 나아 보이는가”를 빠르게 보는 목적이다.

결정:

- 기본 루프는 `benchmarks/profiles/dev_fast.json`으로 고정한다.
- release-grade 검증만 `benchmarks/profiles/release_generalization.json`을 사용한다.
- 캐시는 두 층으로 분리한다.
  - `stores/...`
  - `context_cache/...`
- 같은 보고서 / 같은 청킹 / 같은 ingest mode 재실행에서는 contextual ingest를 다시 호출하지 않는다.
- release run은 회사별 job으로 분리하고 partial summary를 허용한다.

검증 메모:

- `dev_fast_cache_check_2026-04-17`에서 삼성전자 1회사 screening-only를 2회 연속 실행했다.
- 1차 run은 약 `13분 16초`, 2차 run은 약 `5분 27초`였다.
- 2차 run에서는 모든 후보가 `cache_hit = true`, `cache_level = store`, `ingest.api_calls = 0`으로 기록됐다.

효과:

- 일상 실험에서 가장 비싼 ingest 비용을 반복해서 내지 않게 됐다.
- release run도 회사별 job으로 쪼개 partial summary를 남길 수 있게 되어 timeout 리스크가 줄었다.

### 결정 11. 운영 기본값은 당분간 `contextual_all_2500_320`을 유지한다

배경:

- `v4_generalization_fix_2026-04-17`까지 완료한 결과, 저비용 후보가 비용 절감 자체는 분명했지만 3개 기업 공통 screening quality floor를 넘지 못했다.
- 저비용 후보의 실패는 단순 ingest 비용보다 query-stage abstention과 category-specific retrieval miss로 나타났다.

결정:

- 기본 운영 baseline은 계속 `contextual_all_2500_320`으로 둔다.
- `contextual_parent_only`, `contextual_selective_v2`, `contextual_parent_hybrid`는 benchmark 전용 후보로 유지한다.
- 다음 최적화 우선순위는 ingest mode 추가보다 아래에 둔다.
  - numeric / risk / R&D abstention 완화
  - NAVER business overview retrieval 개선
  - missing-information hallucination 억제

근거:

- `contextual_parent_only_2500_320`
  - 평균 `API calls -86.0%`
  - 평균 `ingest time -84.7%`
  - 하지만 numeric / risk / R&D smoke abstention 반복
- `contextual_selective_v2_2500_320`
  - 평균 `API calls -59.6%`
  - 평균 `ingest time -61.6%`
  - 하지만 business overview / risk miss 반복
- `contextual_parent_hybrid_2500_320`
  - 일부 품질 보완은 있으나 평균 비용 이점이 없고 baseline보다 비싼 경우가 있음
- `contextual_all_2500_320`
  - 비용은 가장 크지만 현재까지 가장 일관된 baseline

효과:

- 기본값 변경을 성급하게 하지 않고, 이후 실험을 “더 싼 ingest”보다 “실패 유형 제거” 중심으로 정렬할 수 있게 됐다.

---

## 운영 메모

- Python 3.14 환경에서는 `langchain_core` 관련 경고가 남아 있다.
- `langchain_community.vectorstores.Chroma` deprecation 경고도 남아 있다.
- Hugging Face cache와 local benchmark store는 `.gitignore`로 제외한다.
