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

---

## v4 결과 기반 query-stage 실패 개선

### 결정 39: Evidence 하드 abstain 방지 — docs 상한 확대 + missing fallback

**문제**: Hit@k=1.0임에도 agent가 "근거를 찾지 못했습니다"를 반환하는 케이스 발생.
NAVER `numeric_fact_001` (영업수익) 등.

**근본 원인**:
- `_extract_evidence()`가 `docs[:6]`만 evidence LLM에 전달
- 정답 청크가 7~8위에 있으면 evidence LLM에 아예 전달되지 않음
- structured output이 `coverage=missing`을 반환하면 `evidence_bullets=[]` → `_analyze()`에서 하드 abstain

**해결책**:
1. `docs[:6]` → `docs[:8]`로 확대
2. `coverage=missing` + docs 존재 시 하드 abstain 대신 deterministic fallback 실행
   - `docs[:6]`에서 `[section_path] page_content[:220]` 스니펫 추출 → `evidence_status=sparse`로 전달
   - `_deterministic_fallback()` 헬퍼로 분리, exception 경로와 missing 경로 공유

**결과**: 검색은 성공했는데 evidence 단계에서 abstain하는 경우를 sparse 답변으로 대체

---

### 결정 40: Analyze 프롬프트 — risk 과잉 추론 및 "확인되지 않습니다" 남발 억제

**문제**: SK하이닉스 `risk_analysis_001`에서 faithfulness=0.0.
Evidence에 시장위험·신용위험·유동성위험이 정확히 있는데, 최종 답변이 "가격위험이 법인세비용차감전순이익에 미치는 잠재 영향은 확인되지 않습니다" 같은 문장을 반복적으로 추가.

**근본 원인**:
- `risk` instruction: "배경과 잠재 영향을 설명하세요" → LLM이 문서에 없는 영향을 추론
- `"질문에 필요한 정보가 충분하지 않으면 확인되지 않는다는 식으로 답하세요"` 규칙이 개별 하위 항목에 적용됨
- `coverage: sparse` raw 값이 프롬프트에 노출되어 LLM이 과도한 부재 명시를 유도받음

**해결책**:
1. `risk` instruction: "배경과 잠재 영향" 제거 → "공시에 명시된 항목만 정리"
2. "확인되지 않습니다" 사용 조건을 "질문 전체에 답할 근거가 없을 때만"으로 제한
3. `coverage`를 raw로 노출하던 방식 → `coverage_note` 딕셔너리로 변환
   - `sufficient` → 빈 문자열 (불필요한 노이즈 제거)
   - `sparse` → 짧은 힌트 한 줄
   - `conflicting` → 상충 명시 안내

---

### 결정 41: query_type 6종 확장 + 표/단락 분리 retrieval 레인

**문제**: `qa`가 catch-all로 수치 쿼리(numeric_fact)와 개요 쿼리(business_overview)를 모두 포함.
표 청크가 RRF에서 상위를 점령해 business_overview 질문에서 Hit@k=0.0 발생.
기존 C 해결책(keyword frozenset)은 rule-based hardcoding.

**해결책**:

**1. `QueryClassification` 4종 → 6종**:
- 기존: `qa`, `comparison`, `trend`, `risk`
- 추가: `numeric_fact` (수치·금액 중심), `business_overview` (사업 구조·개요)
- `qa`는 어느 유형에도 해당하지 않는 일반 질의 catch-all로 축소

**2. `_classify_query` 프롬프트 보강**:
- 각 타입별 판별 기준 + 구체 예시 추가 (zero-shot → few-shot 형태)

**3. `_rerank_docs` keyword hardcoding 제거**:
- `_NUMERIC_QUERY_SIGNALS`, `_OVERVIEW_QUERY_SIGNALS` frozenset 삭제
- `_TABLE_PREFERRED_TYPES = {"numeric_fact", "trend"}` / `_PARAGRAPH_PREFERRED_TYPES = {"business_overview", "risk", "qa"}`
- 표 청크 패널티 `-0.08` / 단락 청크 패널티 `-0.04` — `state["query_type"]` 기반 적용

**4. `_retrieve` 분리 레인**:
- `TABLE_PREFERRED`: 표 우선, 단락 최소 2개 보장
- `PARAGRAPH_PREFERRED`: 단락 최소 `k//2`개 보장
- `comparison`: 비율 제한 없음

**5. `_analyze` instruction 6종으로 세분화**:
- `numeric_fact`: 수치 정확히 + 출처 앵커
- `business_overview`: 항목별 서술
- 기존 `risk`/`comparison`/`trend`/`qa` 유지

**검증**: 분류 8/8 정확, 분리 레인 mock 테스트 통과

---

## 결정 42 — v5 benchmark 실행 및 faithfulness 하락 원인 분석 (2026-04-20)

**문제**: 결정 39~41 반영 후 v5 full eval에서 faithfulness가 v4(0.660) → v5(0.380)로 하락.
retrieval 수치(hit@k, section, citation, context_recall)는 동일하게 유지됨.

**원인**:

1. **`risk` evidence LLM 할루시네이션**: `_extract_evidence`에서 LLM이 DART 원문에 없는 리스크 카테고리명(예: "운영위험")을 자체 금융 지식으로 추가 → `_analyze`가 이를 그대로 출력 → faithfulness evaluator가 원문에 없는 내용으로 판정해 0.0.
2. **`business_overview` 검색 레인 변경**: 결정 41(Fix C)로 검색 결과가 바뀌어 v5 답변 구조가 v4와 달라짐 → stochastic judge 편차 반영.
3. **Evaluator context 범위 불일치**: `_compute_faithfulness`가 `contexts[:5]`를 사용하지만 agent는 `docs[:8]`을 실제로 사용 → evaluator가 실제 근거를 일부 제외한 채 판정.

**해결책**:

**A. `_extract_evidence` — risk 타입 verbatim 제한** (`src/agent/financial_graph.py`):
- `query_type == "risk"`일 때 `extra_rules` 추가:
  "리스크 유형명은 컨텍스트에 명시된 단어만 사용, 컨텍스트에 없는 리스크 카테고리를 새로 만들지 마세요"
- `extra_rules`를 prompt 및 invoke에 전달

**B. `_analyze` — sparse evidence 보수적 지침** (`src/agent/financial_graph.py`):
- `evidence_status == "sparse"`(deterministic fallback 결과)일 때 별도 instruction 적용:
  "근거 문장에 명시된 내용만 그대로 인용, 카테고리 새로 만들거나 없는 항목 추가 금지"
- `coverage_note` 없애고 instruction만 사용

**C. `_classify_query` 프롬프트 보강** (`src/agent/financial_graph.py`):
- `numeric_fact` vs `business_overview` 판별 기준 명확화:
  "사업 구조 파악이 목적이면 수치를 포함하더라도 business_overview"
- 사업부문 비중, 자회사 수 등 예시 추가

**D. Evaluator context 확장** (`src/ops/evaluator.py`):
- `_compute_faithfulness`에서 `contexts[:5]` → `contexts[:8]`로 확장
- agent 실제 사용 범위(docs[:8])와 일치시켜 평가 일관성 확보

**결과**: 코드 수정 완료. 재실험 필요.

---

## 결정 43 — score 최적화보다 principled answer generation을 우선한다

**문제**: `v6` / `v7` faithfulness 보정 실험에서 일부 `business_overview` 문항은 회복됐지만, 같은 수정이 `risk` 문항에는 새 부작용을 만들었다. 이는 answer-stage rule을 계속 추가하는 방식이 benchmark score를 국소적으로 올릴 수는 있어도, 장기적으로는 시스템을 더 복잡하고 덜 일반화 가능하게 만들 수 있음을 보여준다.

**관찰**:

1. retrieval 계열 지표는 큰 변화가 없는데 faithfulness만 크게 흔들릴 수 있었다.
2. 이는 retrieval보다 answer synthesis / judge interaction이 더 큰 문제 축이라는 뜻이다.
3. `question_type` / 질문 표현 / 출력 길이별 세부 규칙을 계속 늘리면 특정 benchmark 문항에는 유리하지만 다른 문항에서 부작용이 생긴다.
4. `numeric_fact_001`처럼 metric 해석을 왜곡하는 canonical answer 형식 문제도 일부 존재한다.

**결정**:

- 앞으로는 answer-stage hardcoded rule을 계속 늘리는 방향으로 가지 않는다.
- 최근 규칙은 아래처럼 분리해서 관리한다.
  - 유지:
    - `docs[:8]` evidence 입력 확대
    - missing fallback
    - risk evidence verbatim 제한
    - evaluator context 정합성 수정
  - 실험용:
    - query_type별 section bias
    - query_type별 output style
    - post-generation guard pass
  - 제거 후보:
    - `"얼마"`, `"몇 개"` 같은 질문 표현 기반 세부 분기
    - 특정 benchmark 문항 judge 성향에 맞춘 형식 조정
- 다음 단계는 규칙 추가가 아니라 answer generation 구조를 더 단순하고 설명 가능하게 바꾸는 쪽으로 잡는다.

**실행 원칙**:

1. answer 생성은 “새 답을 쓰는 단계”가 아니라 “evidence를 질문 범위에 맞게 압축하는 단계”로 본다.
2. faithfulness는 중요하지만 단독 목표로 최적화하지 않는다.
3. benchmark-only 최적화와 운영 기본값 후보를 분리해서 해석한다.
4. canonical eval dataset과 judge rubric도 시스템과 함께 개선 대상으로 본다.

참조:

- [docs/answer_generation_principles.md](docs/answer_generation_principles.md)
- `v6_faithfulness_guard_2026-04-20`
- `v7_faithfulness_guard_refine_2026-04-20`

---

## 결정 44 — 숫자 질문 평가는 일반 faithfulness judge와 분리한다

**문제**: `numeric_fact_001`처럼 답이 사실상 맞는데도 `faithfulness = 0.0`이 나오는 false fail이 반복됐다.

대표 사례:

- canonical answer / evidence 표현: `300조 8,709억원`
- model answer 표현: `300,870,903 백만원`

사람 기준으로는 동치 값이지만, 현재 서술형 `faithfulness` judge는 이 차이를 안정적으로 인정하지 못한다. 이건 generation만의 문제가 아니라 **evaluator가 숫자 동치성, grounding, target field 적합성을 한 번에 처리하려다 생기는 구조적 한계**로 본다.

**관찰**:

1. retrieval support와 runtime evidence는 충분한데 `faithfulness`만 0.0이 되는 케이스가 존재했다.
2. structured runtime evidence를 추가한 뒤에도 동일 현상이 재현됐다.
3. 이 상태에서 generation rule을 더 붙이면 metric gaming으로 흐르기 쉽다.

**결정**:

- `numeric_fact`는 일반 서술형 `faithfulness` 하나로 채점하지 않는다.
- 숫자 질문은 별도 evaluator path로 분리한다.
- 목표 구조는 아래 병렬 evaluator + resolver다.
  - `Numeric Extractor`
  - `Numeric Equivalence Checker`
  - `Grounding Judge`
  - `Retrieval Support Check`
  - `Conflict Resolver`
- 최종 판정은 `PASS / FAIL / UNCERTAIN`으로 둔다.
- 기존 `faithfulness`는 숫자 질문에서 보조 지표로만 유지한다.

**효과**:

- 숫자 표현 방식 차이로 인한 false fail을 줄일 수 있다.
- 값 동치성, grounding, retrieval support를 분리해 설명 가능성이 높아진다.
- generation rule을 계속 누적하지 않고도 numeric evaluation의 신뢰도를 높일 수 있다.

참조:

- [docs/numeric_evaluation_architecture.md](docs/numeric_evaluation_architecture.md)

---

## 결정 45 — numeric evaluator를 구현하고 numeric_fact의 주 판정으로 사용한다

**문제**: 결정 44에서 방향을 정리했지만, 실제 benchmark 결과 해석에서는 여전히 `faithfulness = 0.0` 같은 숫자가 먼저 보이기 때문에, false fail 케이스가 다시 “generation 문제”처럼 읽힐 위험이 있었다.

**구현**:

- `src/ops/evaluator.py`
  - `Numeric Extractor`
  - `Numeric Equivalence Checker`
  - `Grounding Judge`
  - `Retrieval Support Check`
  - `Conflict Resolver`
- `src/ops/benchmark_runner.py`
  - per-question 결과에 아래 필드 직렬화
    - `numeric_equivalence`
    - `numeric_grounding`
    - `numeric_retrieval_support`
    - `numeric_final_judgement`
    - `numeric_confidence`
  - `review.csv`, `review.md`에도 numeric evaluator 결과 표시

**검증**:

- `dev_fast_fulleval`로 삼성전자 1회사 재실행
- `numeric_fact_001` 결과:
  - generic `faithfulness = 0.0`
  - `numeric_equivalence = 1.0`
  - `numeric_grounding = 1.0`
  - `numeric_retrieval_support = 1.0`
  - `numeric_final_judgement = PASS`

**결정**:

- `numeric_fact` 해석에서는 generic `faithfulness`를 주 판정으로 쓰지 않는다.
- 숫자 질문의 주 판정은 `numeric_final_judgement`로 두고,
  - `faithfulness`
  - `context_recall`
  - `retrieval_hit_at_k`
  는 보조 참고치로 본다.
- 다음 단계는 numeric evaluator 자체를 더 키우는 것보다:
  - aggregate / summary에서의 노출
  - `PASS / FAIL / UNCERTAIN` 해석 규칙
  - cross-company summary 반영
  을 정리하는 것이다.

**효과**:

- 숫자 false fail을 generation regression으로 오해하는 일을 줄일 수 있다.
- benchmark 결과를 “generic faithfulness”와 “numeric correctness/grounding” 두 축으로 더 정확히 읽을 수 있다.

---

## 결정 46 — compression / validation의 typed output을 benchmark artifact까지 연결한다

**문제**: `structured evidence`와 `compression -> validation` 구조를 도입했지만, 결과 artifact에는 여전히 최종 answer 문자열과 runtime evidence만 남아 있었다. 이 상태로는 `business_overview`나 `risk`에서 왜 점수가 흔들리는지, 어떤 claim을 선택했고 무엇을 버렸는지 설명하기 어려웠다.

**구현**:

- `src/agent/financial_graph.py`
  - `CompressionOutput`
    - `selected_claim_ids`
    - `draft_points`
    - `draft_answer`
  - `ValidationOutput`
    - `kept_claim_ids`
    - `dropped_claim_ids`
    - `unsupported_sentences`
    - `final_answer`
  - `agent.run()` 결과에도 위 필드 전달
- `src/ops/evaluator.py`
  - per-question 결과에 claim selection / drop 정보 저장
- `src/ops/benchmark_runner.py`
  - `results.json`, `review.csv`, `review.md`에 새 필드 직렬화

동시에 제거한 것:

- 질문 wording을 직접 읽어 output style을 바꾸던 local optimization

**결정**:

- 앞으로 `compression -> validation`은 문자열만 반환하는 단계로 보지 않는다.
- reviewer artifact는 answer 자체뿐 아니라
  - 어떤 claim을 선택했는지
  - 어떤 claim을 버렸는지
  - 어떤 문장을 unsupported로 제거했는지
  를 함께 보여줘야 한다.
- 다음 benchmark부터는 `business_overview` / `risk` 회귀를 metric만이 아니라 claim 흐름까지 포함해 해석한다.

**효과**:

- failure analysis가 더 설명 가능해진다.
- hardcoded rule 추가 없이도, answer가 왜 그렇게 나왔는지 추적할 수 있다.
- 다음 단계의 중심이 “점수 올리기”가 아니라 “compression / validation 품질 해석”으로 이동한다.
## 최근 결정 추가 메모

### 결정 49 — sentence-level validator는 유지하되, 다음 단계의 중심은 validator 강도 강화가 아니라 claim selection 구조화로 둔다

배경:

- typed compression / validation output은 reviewer artifact에 안정적으로 남는다.
- sentence-level validator를 넣은 뒤 실제 pruning도 일부 발생했다.
- 하지만 5문항 full eval 기준으로는 retrieval / citation 개선에 비해 answer quality 개선은 약했고,
  validator가 아직 충분히 많은 문장을 잘라내지 못했다.

판단:

- validator 자체는 유지한다.
- 다만 다음 단계는 `drop_overextended` / `drop_redundant`를 더 늘리는 것이 아니라,
  `business_overview` / `risk`에서 애초에 잘못된 claim 조합이 선택되지 않게 하는 데 둔다.

다음 단계:

- evidence에 `claim_type` / `topic_key` 추가
- `business_overview`
  - `DX / DS / SDC / Harman` 대표 claim selection
- `risk`
  - 상위 taxonomy claim과 세부 risk item claim 동시 선택 방지
- top-N evidence selection 대신 group-wise selection 도입
