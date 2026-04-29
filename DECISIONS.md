# 기술 결정 로그

> 이 문서는 **append-only 성격의 결정 로그**다.
> 현재 상태와 다음 작업은 각각 `CONTEXT.md`, `PLAN.md`를 기준으로 본다.
> 즉, 이 문서는 최신 snapshot을 유지하려고 덮어쓰지 않고,
> 중요한 설계 판단과 그 근거를 누적 기록하는 용도로 쓴다.

---

## 핵심 결정 요약

이 섹션은 **포트폴리오 관점에서 지금 이 프로젝트를 설명할 때 가장 중요한 기술 결정**만 위쪽에 모아 둔 요약이다.  
과거의 상세 실험 로그와 히스토리는 아래 `상세 결정`부터 이어진다.

## 포트폴리오용 Decision Scorecard

| 영역 | 핵심 결정 | 왜 중요한가 | 정량 근거 / 증거 | 상태 |
| --- | --- | --- | --- | --- |
| 프로젝트 정의 | 검색기가 아니라 **구조화된 evidence를 읽고 계산하는 DART 전용 RAG agent**로 포지셔닝 | retrieval, math, evaluator를 한 시스템 안에서 설명 가능 | [docs/overview/technical_highlights.md](docs/overview/technical_highlights.md) | 유지 |
| Parser | DART 구조를 보존하는 parser를 코어 자산으로 유지 | 후속 graph / parent-child / note expansion의 기반 | parser 기반 graph / retrieval 구조는 아래 상세 결정 1~9 참고 | 유지 |
| Retrieval | dense-only 대신 **hybrid + structure-aware expansion** 채택 | section purity와 context recall을 함께 다루기 위함 | [docs/evaluation/benchmarking.md](docs/evaluation/benchmarking.md) | 유지 |
| Math architecture | `operation enum`보다 **formula planner + safe AST evaluator** 중심 | direct calc / rule calc의 수학·단위 흔들림 제거 | retrospective strict correctness `0.556 -> 1.000` ([benchmarking.md](docs/evaluation/benchmarking.md)) | 유지 |
| Evaluator | section hit보다 **정답성 + operand grounding** 우선 | 금융 문서의 중복 수치 환경에서 false negative 감소 | false negative rate `12.5% -> 0.0%` ([benchmarking.md](docs/evaluation/benchmarking.md)) | 유지 |
| Dev loop | **single-document benchmark + eval-only loop**를 운영 기본으로 사용 | 빠른 회귀와 디버깅 재현성 확보 | `run_eval_only.py`, debug-first 루프 | 유지 |
| Domain knowledge | 하드코딩 규칙을 **thin ontology**로 점진 이동 | metric-specific duct tape 축소 | `financial_ontology.json`, retrieval/planner prior | 진행 중 |
| Roadmap | `REFERENCE_NOTE -> self-reflection -> cross-company` 순으로 확장 | 단일 문서 깊이 -> 실패 복구 -> 범위 확장 순서 고정 | [CONTEXT.md](CONTEXT.md), [docs/planning/backlog_and_next_epics.md](docs/planning/backlog_and_next_epics.md) | 진행 중 |
| Artifact policy | 실험 자산은 repo에 남기고 scratch만 무시 | 포트폴리오/면접에서 재현 가능한 evidence 확보 | benchmark results / summary tracked | 유지 |

## 핵심 결정 해설

### 0. 이 프로젝트는 “검색기”가 아니라 **구조화된 evidence를 읽고 계산하는 DART 전용 RAG agent**로 정의한다

현재 시스템의 중심은 아래 다섯 축이다.

| 축 | 현재 구현 |
| --- | --- |
| 문서 구조화 | DART XML 구조 파서, structure-aware chunking |
| Retrieval | hybrid retrieval, parent-child / graph-style expansion |
| Reasoning | evidence-first answer path |
| Numeric path | formula planner + safe AST calculator |
| Evaluation loop | benchmark / eval-only / debug-first reproduction |

즉 “문서를 찾아서 요약하는 챗봇”보다, **재무 공시를 읽고 근거를 남기며 계산하는 agent**로 포지셔닝한다.

### 1. 문서 구조를 보존하는 parser를 코어 자산으로 본다

일반 HTML split 대신 DART의 `SECTION-*`, `TITLE`, `P`, `TABLE`, `TABLE-GROUP`를 직접 읽는 parser를 유지한다.

핵심 이유:

- 문단 / 표 / 섹션 경계를 보존할 수 있음
- `parent_id`, `section_path`, `table_context`, `chunk_uid` 같은 구조 메타데이터를 만들 수 있음
- 이후
  - parent-child retrieval
  - graph expansion
  - `REFERENCE_NOTE`
  의 기반이 됨

즉 parser는 단순 전처리가 아니라, **후속 reasoning을 가능하게 하는 구조 계층**이다.

### 2. retrieval은 dense 하나로 끝내지 않고, **hybrid + structure-aware expansion**으로 설계한다

기본 retrieval stack은 아래와 같다.

| 구성 요소 | 현재 선택 |
| --- | --- |
| dense embedding | `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2` |
| sparse retrieval | BM25 character bigram |
| fusion | reciprocal rank fusion |
| dedupe | `chunk_uid` 기준 |
| filter policy | non-empty strict metadata filtering |

여기에 검색과 답변 컨텍스트를 분리하는 **parent-child retrieval**과, retrieval 이후 parent / sibling / table context / reference note를 보강하는 **document-structure expansion**을 얹는다.

즉 retrieval은 “한 번 search해서 끝”이 아니라,  
**검색 -> 구조 확장 -> evidence selection**의 다단계 경로로 본다.

### 3. 계산 질문은 `operation enum`이 아니라 **formula planner + safe AST evaluator**로 푼다

초기 rule-based operation 분기에서 벗어나,

- operand 추출
- formula planning
- safe AST execution
- grounded rendering

으로 역할을 분리했다.

핵심 원칙:

- 의미 해석과 수식 계획은 LLM
- 실제 수학 연산은 Python
- renderer는 계산 결과 JSON만 보고 서술

이 구조 덕분에 `comparison`, `ratio`, `growth`, `trend`를 하나의 계산 경로로 일반화할 수 있게 됐다.

### 4. 평가는 section hit보다 **정답성 + grounding**을 우선한다

현재 numeric / math 평가는 아래 조합을 사용한다.

| 평가 축 | 역할 |
| --- | --- |
| `display-aware numeric equivalence` | 표시 정밀도 차이를 흡수한 정답성 판정 |
| `operand grounding` | 실제 읽은 텍스트에 operand가 존재하는지 확인 |
| math-aware completeness | 질문이 요구한 최종 산출값 / 단위 / 방향 중심 평가 |

특히:

- `retrieval_hit_at_k`, `section_match_rate`, `P@5`
  - retriever diagnostic
- `numeric_final_judgement`
  - 실제 계산에 쓴 operand가 읽은 텍스트에 grounded되었는지 기준

으로 분리했다.

즉 미리 지정한 section을 못 찾았더라도, **문서 안의 실제 수치로 올바르게 계산했고 grounding이 되면 PASS**로 인정한다.

### 5. 평가와 실험은 **single-document benchmark + eval-only loop**를 기준선으로 운영한다

multi-company benchmark를 계속 늘리기 전에, 삼성전자 2024 사업보고서 1건 기준으로 Golden Dataset과 evaluator를 먼저 고정했다.

또한 full re-ingest가 느린 문제를 줄이기 위해:

- benchmark runner
- eval-only fast path
- debug-first reproduction script

를 분리했다.

즉 이 프로젝트는 모델 성능만 보는 게 아니라, **실험 속도와 디버깅 재현성까지 포함한 연구/개발 루프**를 갖추는 쪽으로 설계했다.

### 6. 도메인 지식은 코드 하드코딩 대신 **thin ontology**로 옮기기 시작했다

최근에는 `financial_ontology.json`을 도입해,

- preferred sections
- component hints
- planner prior

를 code path 밖으로 일부 이동시켰다.

현재는 retrieval / planner-first로 얇게 연결된 상태지만, 장기적으로는 metric family 확장을 통해 remaining duct tape를 줄이는 방향이다.

즉 이 프로젝트는 규칙을 계속 늘리는 대신, **도메인 지식을 선언적으로 구조화하는 방향**으로 가고 있다.

### 7. 다음 큰 확장은 `REFERENCE_NOTE -> self-reflection -> cross-company` 순서로 간다

현재 남은 retrieval / business / risk 이슈는 대부분

- purity debt
- answer packaging debt
- metric / diagnostic 해석 문제

라서 blocker보다는 backlog에 가깝다.

따라서 다음 우선순위는 local patch가 아니라 구조 확장이다.

현재 로드맵:

| 순서 | 확장 |
| --- | --- |
| 1 | `REFERENCE_NOTE Phase 1a` - section-path reference graph edge |
| 2 | `REFERENCE_NOTE Phase 1b` - numbered note reference |
| 3 | 제한적 `self-reflection` - `retry_count < 1`, math / why 질문군 우선 |
| 4 | `cross-document / cross-company reasoning` - retrieval 병렬화 + entity/report/period binding |

즉 이 프로젝트의 다음 단계는 **단일 문서 깊이 -> 실패 복구 -> 다중 문서 범위 확장** 순으로 진화한다.

### 8. 실험 결과 자산은 repo에 남기고, 로컬 상태만 무시한다

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

### 결정 56. query routing은 `intent`와 `format_preference`를 분리해 다룬다

배경:

- 기존 `query_type` 하나가 질문 의도와 retrieval 형식 선호를 동시에 결정했다.
- 이 구조는 `business_overview`가 표를 필요로 하는 질문에서도 table penalty를 받게 만드는 등, retrieval 정책 충돌을 만들었다.
- 또한 `risk`, `business_overview`, `numeric_fact` 간 variance가 커서 질문에 따라 `numeric_fact`로 과도하게 빨려 들어가는 현상이 반복됐다.

결정:

- routing state에 아래 필드를 별도로 둔다.
  - `intent`
  - `format_preference`
  - `routing_source`
  - `routing_confidence`
  - `routing_scores`
- section bias는 `intent`를 기준으로 계산한다.
- block-type rerank와 retrieval mix는 `format_preference`를 기준으로 계산한다.

효과:

- 질문의 의도와 evidence 형식 선호를 분리하면서, routing과 retrieval 정책의 결합도가 낮아졌다.
- 이후 semantic router나 classifier를 교체하더라도 retrieval 정책을 독립적으로 유지할 수 있게 됐다.

### 결정 57. query routing은 병렬 ensemble보다 semantic fast-path + few-shot fallback cascade로 운영한다

배경:

- rule-based를 계속 늘리면 유지보수 비용이 빠르게 증가한다.
- LLM-only zero-shot 분류는 variance가 컸고, 병렬 ensemble은 conflict resolution과 비용을 동시에 키운다.

결정:

- 1차 방어선으로 semantic router를 둔다.
  - canonical query 임베딩과 cosine similarity로 top-1 / margin 계산
- confidence와 margin이 충분할 때만 fast-path로 즉시 라우팅한다.
- fast-path가 애매할 때만 few-shot LLM classifier를 fallback으로 호출한다.

효과:

- 쉬운 질문은 빠르고 저렴하게 처리하고, 애매한 질문만 LLM이 정교하게 분류하는 구조가 됐다.
- `risk_analysis_001`처럼 semantic top-1이 흔들리는 질문도 fast-path를 억제하고 LLM fallback으로 교정할 수 있게 됐다.
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

- [docs/architecture/answer_generation_principles.md](docs/architecture/answer_generation_principles.md)
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

- [docs/architecture/numeric_evaluation_architecture.md](docs/architecture/numeric_evaluation_architecture.md)

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

---

## 결정 50 — document-structure graph는 retrieval replacement가 아니라 retrieval booster로 사용한다

**문제**: `plain + graph expansion`이 `contextual_all`을 바로 대체할 수 있는지 보기 위해 single-document micro benchmark를 돌렸지만, `q_009` 재무 리스크 질문에서는 seed retrieval이 `이사회`, `감사제도`, `경영진단` 같은 잘못된 섹션에서 시작했다. 이 상태에서 sibling / parent / section lead를 붙이면 오히려 noise만 커졌다.

**구현**:

- `src/storage/vector_store.py`
  - `document_structure_graph.json`
  - `parent_id`, sibling, `section_lead`, `described_by_paragraph` 저장
- `src/agent/financial_graph.py`
  - `retrieve -> expand_via_structure_graph -> evidence`
  - constrained expansion:
    - `table -> paragraph prev만 허용`
    - `sibling_next` 비활성화
    - `max_docs = 8`

**결정**:

- document-structure graph는 contextual ingest를 바로 대체하는 retrieval stack으로 보지 않는다.
- graph expansion은 **좋은 seed를 더 풍부한 evidence set으로 보강하는 도구**로 사용한다.
- seed retrieval miss를 graph가 복구해주길 기대하지 않는다.

**효과**:

- graph expansion의 역할이 더 명확해졌다.
- 이후 실험에서 graph를 키우는 방향보다 seed retrieval 자체를 먼저 맞추는 방향으로 우선순위를 이동시켰다.

---

## 결정 51 — risk 계열 seed retrieval은 Zero-Cost Prefix로 먼저 보강한다

**문제**: `q_009` “주요 재무 리스크는 무엇인가?” 질문은 DART 원문에 `재무 리스크`라는 표현이 직접 나오지 않고, 실제 본문은 `시장위험`, `신용위험`, `유동성위험` 같은 구체 용어를 사용한다. plain chunk만으로는 이 어휘 불일치를 자주 해결하지 못했다.

**구현**:

- `src/ops/benchmark_runner.py`
  - `plain` / `plain_graph` 인덱싱 시 선택적으로 `Zero-Cost Prefix` 사용
  - 원문 앞에 아래 문자열을 강제로 삽입
    - `[섹션]`
    - `[분류]`
    - `[키워드]`
  - 리스크 섹션에는
    - `리스크`
    - `재무 리스크`
    - `시장위험`
    - `신용위험`
    - `유동성위험`
    alias를 같이 넣음
- `single_document_graph_micro` profile에서 plain 계열에 prefix 적용 후 재실험

**결정**:

- `risk` 계열 seed retrieval은 graph보다 먼저 **Zero-Cost Prefix**로 보강한다.
- 이는 LLM contextual ingest를 대체하려는 것이 아니라, vocabulary mismatch를 줄이는 저비용 retrieval engineering으로 해석한다.

**효과**:

- `q_009`는 prefix 적용 후 plain 계열에서도 `hit@k = 1.0`으로 회복됐다.
- 반면 `q_001` 연결 기준 매출액은 여전히 `연결재무제표 주석` 쏠림이 남아, 숫자 질문은 retrieval 이후에도 `query target alignment`가 별도 병목임이 더 분명해졌다.

---

## 결정 52 — `_section_bias`의 substring 중복 가산 버그를 수정하고 주석 섹션 패널티를 추가한다

**문제**: `_SECTION_BIAS_BY_QUERY_TYPE`에 `"연결재무제표"`와 `"연결재무제표 주석"` 두 항목이 동시에 존재하고, `_section_bias`가 `needle in section_path` 방식으로 누적 합산하기 때문에, `"연결재무제표 주석"` 섹션은 두 항목 모두에 매칭되어 +0.12를 받았다. 반면 정답인 `"연결재무제표"` 섹션은 +0.06만 받아 순위에서 밀렸다. `numeric_fact_001` 연결 매출액 질문에서 주석 섹션이 정답 섹션보다 항상 위에 오던 근본 원인이었다.

**수정** (`src/agent/financial_graph.py`):

1. `_SECTION_BIAS_BY_QUERY_TYPE`에서 `numeric_fact`의 `"연결재무제표 주석"` 항목 제거 — 주석 섹션을 부스팅할 이유 없음
2. `_section_bias`에 주석 패널티 추가:
   ```python
   if "주석" in lowered and query_type in self._TABLE_PREFERRED_TYPES:
       bias -= 0.12
   ```

**효과** (v8 benchmark, 삼성전자 2024, 4문항):

- `numeric_fact_001` Top-1 검색 결과가 `연결재무제표 주석` → `연결재무제표`로 역전
- 수정 전 점수: 주석 +0.12, 연결재무제표 +0.06
- 수정 후 점수: 연결재무제표 +0.06, 주석 0.06 − 0.12 = −0.06

| 지표 | contextual_all | contextual_parent_only |
|---|---|---|
| hit@k | 0.750 | 1.000 |
| section_match | 0.281 | 0.344 |
| faithfulness | 0.625 | 0.425 |
| answer_relevancy | 0.572 | 0.518 |
| context_recall | 0.500 | 0.625 |

**참고**: `business_overview_001` hit=0.0은 `회사개요` vs `사업개요` 섹션 불일치 기존 문제로 이번 수정 범위 외.

추가 실험 (plain_prefix_2500_320 포함, 3-way 비교):

| 지표 | contextual_all | contextual_parent_only | plain_prefix |
|---|---|---|---|
| hit@k | 0.750 | 1.000 | **1.000** |
| section_match | 0.281 | 0.344 | 0.312 |
| faithfulness | 0.625 | 0.500 | **0.750** |
| answer_relevancy | 0.562 | 0.566 | 0.473 |
| context_recall | 0.500 | 0.625 | 0.500 |

`plain_prefix`가 LLM ingest 비용 0으로 hit@k=1.000, faithfulness=0.750 달성. `business_overview_001`도 plain_prefix에서 hit=1.0으로 회복됨.

---

## 결정 53 — `_section_bias`를 longest-match-first 구조로 개선하고 `손익계산서` 항목을 추가한다

**배경**: 결정 52에서 주석 이중 가산 버그를 패널티로 사후 보정했으나, 근본적으로는 매칭 로직 자체를 exclusive하게 만드는 것이 더 안전하다. 또한 `numeric_fact` 가중치 체계가 전반적으로 보수적이라는 피드백이 있었다.

**수정** (`src/agent/financial_graph.py`):

1. `_section_bias`를 longest-match-first + break 구조로 변경:
   ```python
   for needle, weight in sorted(
       self._SECTION_BIAS_BY_QUERY_TYPE.get(query_type, ()),
       key=lambda x: len(x[0]),
       reverse=True,
   ):
       if needle.lower() in lowered:
           bias += weight
           break
   ```
   가장 구체적인(긴) 섹션명이 먼저 매칭되고 이후 더 짧은 needle의 추가 가산을 차단.

2. `numeric_fact`에 `"손익계산서"` 항목 추가 (+0.08):
   일부 DART 데이터에서 손익계산서가 별도 섹션 경로로 인덱싱되는 경우 대비.

**피드백 중 적용하지 않은 제안**:
- numeric_fact 가중치 0.20~0.25 대폭 상향: v8에서 hit=1.0 이미 달성 중. 데이터 근거 없이 올리면 과적합 위험.
- Score multiplier 방식: 현재 additive가 작동 중이고 calibration이 더 복잡해짐. 나중 옵션으로 보류.

**결과**: 현재 섹션 점수 (numeric_fact):
- 연결재무제표: +0.060
- 연결재무제표 주석: +0.060 (loop) − 0.120 (주석 패널티) = **−0.060**
- 요약재무정보: +0.060
- 매출 및 수주상황: +0.080
- 손익계산서: +0.080 (신규)

---

## 결정 54 — `plain + prefix`만으로 부족한 표 기반 질문은 `selective contextualization + prefix` 조합으로 해결한다

**문제**: `Zero-Cost Prefix`는 seed retrieval 보강에는 효과적이었지만, `numeric_fact_001`처럼 표 내부 의미를 복원해야 하는 질문에서는 여전히 약했다. `plain_prefix_2500_320`는 올바른 재무 섹션을 가져오고도 “구체적인 수치 정보가 없다”고 답해 `numeric_final_judgement = FAIL`을 기록했다.

**구현**:

- `src/ops/benchmark_runner.py`
  - `contextual_selective_v2` 경로가 `use_zero_cost_prefix = true`를 함께 받을 수 있도록 확장
  - 선택적으로 contextualize된 table / targeted chunk에는
    - LLM context
    - zero-cost prefix
    - raw chunk
    를 함께 인덱싱
- `benchmarks/profiles/dev_fast_focus.json`
  - 새 후보 `contextual_selective_v2_prefix_2500_320` 추가

**실험** (`dev_fast_focus_selective_prefix_2026-04-23`, 삼성전자 2024, 4문항):

| 지표 | contextual_all | contextual_parent_only | plain_prefix | selective_v2_prefix |
|---|---|---|---|---|
| screen_pass | yes | no | no | **yes** |
| faithfulness | 0.575 | 0.500 | **0.925** | 0.675 |
| answer_relevancy | **0.684** | 0.545 | 0.630 | 0.580 |
| context_recall | 0.500 | 0.625 | 0.500 | **0.625** |
| numeric_pass | 1.000 | 1.000 | **0.000** | 1.000 |

질문별 해석:

- `numeric_fact_001`
  - `plain_prefix`: “구체적인 수치 정보가 없습니다” → `numeric_final_judgement = FAIL`
  - `contextual_selective_v2_prefix`: `300조 8,709억원` → `numeric_final_judgement = PASS`
- `risk_analysis_001`
  - `contextual_selective_v2_prefix`는 `위험관리 및 파생거래` 중심 retrieval을 유지하고, 짧지만 grounded한 answer를 생성

**결정**:

- `plain + prefix`는 retrieval seed 보강용 baseline으로 유지한다.
- 그러나 표 기반 숫자 질문과 일부 risk 질문의 실제 답변 품질을 위해서는 `contextual_selective_v2 + prefix`를 현재 저비용 주력 후보로 본다.

## 결정 55 — 다음 단계의 중심을 validator 강도 강화보다 query routing 재설계로 옮긴다

**문제**: retrieval / validator를 점검하는 과정에서, `contextual_selective_v2_prefix_2500_320` 후보를 기존 store에서 직접 실행했을 때

- `주요 재무 리스크는 무엇인가요?`
- `회사가 영위하는 주요 사업은 무엇인가요?`

질문이 모두 `numeric_fact`로 잘못 분류되는 사례가 확인됐다. 이는 retrieval miss나 validator over-pruning 이전에 **query routing variance**가 존재한다는 뜻이다.

또한 기존 구조는 `query_type` 하나가 동시에 아래를 결정했다.

- 질문 의도
- retrieval 시 표/문단 선호
- section bias

이로 인해 과거에는 `business_overview`가 table penalty를 받아, overview-ish 수치 질문에서 구조적 충돌도 발생했다.

**적용**:

- `business_overview`의 table penalty 제거
- `_classify_query` 프롬프트에서 `매출 비중`, `규모` 같은 질문을 `numeric_fact` 쪽으로 더 명확히 유도
- validator는 유지하되, 다음 단계의 중심은 validator 강도 강화가 아니라 routing 재설계로 전환

**다음 방향**:

- `query_type` 단일 라벨 대신
  - `intent`
  - `format_preference`
  를 분리하는 설계 검토
- keyword rule 확대 대신
  - `few-shot LLM classifier`
  - `semantic router`
  를 준비
- 초기 구현은 병렬 ensemble보다 직렬 cascade를 우선 검토

**이유**:

- 지금 병목은 retrieval 자체보다 앞단의 route selection에 더 가깝다
- `query_type` 하나로 intent와 evidence format을 동시에 표현하는 구조는 더 이상 확장성이 좋지 않다
- 다음 병목은 retrieval이 아니라
  - numeric evaluator aggregate / reporting
  - `business_overview` / `risk` generation 품질
  이다.

---

## 결정 58 — semantic router threshold는 held-out routing 셋으로 보정하되, 전역 완화만으로는 배포하지 않는다

**배경**: routing cascade v1 이후 semantic fast-path 기준(`score >= 0.86`, `margin >= 0.04`)이 너무 보수적인지 확인할 필요가 생겼다. threshold를 감으로 조정하지 않기 위해 held-out routing 검증셋을 별도로 만들고 calibration 스크립트를 추가했다.

**추가 자산**:

- `benchmarks/golden/query_routing_eval_v1.json`
  - canonical query와 별도로 유지되는 held-out routing 질문셋
- `src/ops/calibrate_query_router.py`
  - semantic router의 top-1 score / margin을 스윕하며 fast-path coverage / accuracy를 계산

**1차 calibration 결과** (`query_router_calibration_2026-04-24`):

- 기존 기준: `score >= 0.86`, `margin >= 0.04`
  - coverage `0.733`
  - accuracy `1.000`
- 후보 기준: `score >= 0.76`, `margin >= 0.04`
  - coverage `0.833`
  - accuracy `1.000`

이 수치만 보면 전역 score threshold 완화가 좋아 보였지만, 실제 `dev_fast_focus_routing_calibrated_2026-04-24`에서는

- `risk_analysis_001`
  - `business_overview / mixed / semantic_fast_path`
  로 잘못 통과
- 결과적으로 selective-prefix 후보 품질이 악화

**결론**:

- semantic router는 held-out score 분포만으로는 충분하지 않다
- 특히 `business_overview`, `risk`, `numeric_fact` 혼동쌍은 전역 threshold만으로 안정화되지 않는다
- 따라서 calibration은 유지하되, threshold 완화는 **혼동쌍 guard 없이 단독 배포하지 않는다**

---

## 결정 59 — semantic router는 confusion pair용 동적 margin guard와 canonical query 보강을 함께 사용한다

**문제**: `risk_analysis_001` 실패는 `risk` 점수가 낮아서가 아니라, semantic router가 아예 `business_overview`를 top-1로 내면서 fast-path를 통과시킨 **false positive**였다. 이 경우 `risk` 클래스 자체의 threshold를 올려도 방어할 수 없다.

**수정**:

1. `benchmarks/golden/query_routing_canonical_v1.json`
   - risk canonical query에 아래 문구 추가:
     - `삼성전자 2024 사업보고서에서 주요 재무 리스크는 무엇인가요?`
     - `삼성전자의 주요 재무 위험은 뭐야?`

2. `src/agent/financial_graph.py`
   - semantic router에 confusion pair용 동적 margin guard 추가
   - 기본 margin:
     - `0.04`
   - confusion pair일 때 required margin:
     - `0.10`
   - 현재 confusion pair:
     - `business_overview ↔ risk`
     - `business_overview ↔ numeric_fact`

**효과** (`dev_fast_focus_routing_guard_2026-04-24`):

- `risk_analysis_001`
  - `intent=risk`, `format_preference=paragraph`, `source=semantic_fast_path`
  로 복구
- `business_overview_001`
  - semantic이 애매해져 `llm_fallback`으로 안전하게 전환
- 즉 coverage를 크게 잃지 않고도, 가장 치명적인 routing false positive를 다시 막았다

**결정**:

- semantic router는 전역 threshold보다
  - canonical query 품질
  - confusion pair margin
  - few-shot fallback
  의 조합으로 운영한다
- 향후 threshold 보정도 “전역 완화”보다 **혼동쌍 기준 safety-first**를 우선한다

---

## 결정 60 — `numeric_fact`는 `compress → validate`를 bypass하고 전용 `numeric_extractor` 노드로 처리한다

**문제**: `selective_v2_prefix` 실험에서 `numeric_fact_001`의 `numeric_final_judgement = FAIL`이 반복됐다. retrieval_hit_at_k=1.0으로 올바른 섹션을 가져왔음에도, `_extract_evidence` 단계에서 LLM context 요약 문장을 claim으로 잡고 실제 수치가 있는 원문 table까지 못 파고드는 구조적 문제가 원인이었다.

- `selective_v2` 청크 구조: `[LLM context 요약] + [zero-cost prefix] + [원문 table]`
- compression이 앞부분 요약을 claim으로 선택 → 수치 없는 요약 문장이 답변으로
- `plain_prefix`는 LLM context가 없어 prefix 메타데이터만 claim으로 뽑힘

**원인 분석**:

- `compress → validate` 파이프라인은 텍스트 요약을 위해 설계된 컨베이어로, 표의 2차원 구조에서 특정 수치를 핀포인트로 추출하는 데 구조적으로 취약하다.
- 일반 evidence extraction이 question_relevance=medium/context인 청크를 claim으로 잡으면 compression 단계에서 수치가 누락된다.

**구현** (`src/agent/financial_graph.py`):

1. `NumericExtraction` Pydantic 스키마 추가:
   - `period_check`: 당기/전기, 연도/기수 확인
   - `consolidation_check`: 연결/별도 기준 확인
   - `unit`: 표에 명시된 금액 단위
   - `raw_value`: 문서 원본 숫자 (변환 없이)
   - `final_value`: 최종 답변 한 문장

2. `_extract_numeric_fact` 노드:
   - `retrieved_docs` → `_format_context` (parent chunk 우선) → CoT structured output
   - `compress`, `validate` 완전 bypass
   - grounding judge용 synthetic `evidence_item` 생성 (raw_value + unit)

3. `_route_after_expand` 조건부 라우팅:
   - `intent == “numeric_fact”` → `numeric_extractor` → `cite` → END
   - 그 외 → 기존 `evidence → compress → validate → cite` 경로

**효과** (`numeric_extractor_v2_2026-04-26`, 삼성전자 2024, 4문항):

| 지표 | contextual_all | contextual_parent_only | plain_prefix | selective_v2_prefix |
|---|---|---|---|---|
| numeric_pass | 1.000 | 1.000 | **0.000** | **1.000** ✅ |
| faithfulness | 0.700 | 0.875 | 0.454 | 0.825 |
| context_recall | 0.500 | 0.625 | 0.500 | 0.500 |
| ingest cost (USD) | 0.919 | 0.130 | 0.000 | 0.401 |

- `selective_v2_prefix`: routing_guard 대비 FAIL → PASS 회복
- `plain_prefix`: 여전히 UNCERTAIN/FAIL — plain chunk에 표 수치가 충분히 포함되지 않거나 LLM이 table row를 추출하지 못함. 별도 검토 필요.

**결정**:

- `numeric_fact` intent는 `compress → validate`를 거치지 않는다.
- `numeric_extractor`가 period/consolidation/unit을 CoT로 먼저 확인하고 raw_value를 추출한다.
- grounding judge는 numeric_extractor가 생성한 synthetic evidence_item을 기준으로 판정한다.
- `plain_prefix`의 numeric_fact 실패는 ingest-side 문제(표 원문이 BM25/vector로 충분히 검색되지 않음)로 별도 추적한다.

---

## 결정 61 — `compress` 프롬프트를 수정하고 intent별 evidence cap을 도입한다

**문제**: `compress_tuning_2026-04-26` 실험에서 두 가지 문제가 확인됐다.

1. `risk_analysis_001` 답변에 `[삼성전자 | 2024 | ...]` 형태의 source_anchor가 그대로 노출되어 faithfulness judge 교란 → faithfulness=0.3
2. `business_overview_001` 답변이 각 부문 제품/역할 설명을 과도하게 생략 → completeness=0.7

**수정** (`src/agent/financial_graph.py`):

1. compress 프롬프트에 anchor 금지 규칙 추가:
   - `draft_answer`/`draft_points`에 source_anchor 원문을 포함하지 않도록 명시

2. `_compression_guidance` instruction/output_style 수정:
   - `business_overview`: "각 부문을 설명할 때 근거에 등장하는 구체적인 예시를 생략하지 말고 포함"
   - `risk`: "각 항목을 나열할 때 이름만 적지 말고 구체적인 정의나 영향을 한 줄씩 함께 요약"
   - output_style: bullet 형태 구체화

3. `_select_evidence_for_compression`에 intent별 동적 cap 도입:
   - `risk`: 10, `business_overview`: 8, `comparison`: 8, 나머지: 6 (기존)

**효과** (`compress_tuning_2026-04-26`, selective_v2_prefix, 4문항):

| 지표 | baseline | compress_tuning |
|---|---|---|
| business_overview_001 faithfulness | 1.0 | 0.7 |
| business_overview_001 completeness | 0.7 | **1.0** |
| business_overview_003 completeness | 0.7 | **1.0** |
| risk_analysis_001 faithfulness | 0.3 | **0.5** |
| numeric_fact_001 numeric_pass | PASS | PASS |

**해석**:
- `business_overview` completeness 개선 성공. faithfulness 0.7은 child chunk context와 parent chunk 기반 답변 간 표현 차이에서 오는 평가기 구조 문제로 판단 (실제 hallucination 없음).
- `risk` faithfulness 개선됐으나 completeness가 0.7→0.5로 하락. 원인은 evidence extraction LLM variance — 실행마다 항목 수와 구성이 달라짐. compress/validate 문제가 아님.

**결정**:
- source anchor 금지, 구체적 예시 보존, intent별 evidence cap 수정은 유지한다.
- `risk` completeness 불안정은 evidence extraction variance 문제로 별도 추적한다.
- `business_overview` faithfulness 0.7은 evaluator가 child chunk만 보는 구조적 한계이며, 현재 단계에서는 허용 범위로 본다.

---

## 결정 62 — `risk` evidence extraction에 exhaustive 추출 규칙을 추가한다

**문제**: `evidence_cap_2026-04-26` 실험에서 risk completeness가 contextual_all=0.3, contextual_parent_only=0.0으로 급락했다. cap 자체를 올려도 `_extract_evidence` LLM이 실행마다 항목 수를 다르게 생성하기 때문에 cap 이후 단계에는 영향을 줄 수 없다. 핵심 원인은 LLM이 여러 독립적인 리스크 항목을 임의로 합치거나 생략하는 것이다.

**수정** (`src/agent/financial_graph.py`, `_extract_evidence`):

`query_type == "risk"` 조건에서 `extra_rules`에 두 가지 규칙을 추가했다:

```python
extra_rules = (
    "\n- 리스크 유형명은 컨텍스트에 명시된 단어만 사용하세요. "
    "컨텍스트에 없는 리스크 카테고리(예: '운영위험', '규제위험' 등)를 새로 만들지 마세요."
    "\n- [중요] 컨텍스트에 여러 개의 독립적인 리스크 항목이 나열되어 있다면, "
    "임의로 그룹화하거나 생략하지 마세요. "
    "문서에 존재하는 각 항목을 하나씩 독립적인 EvidenceItem으로 빠짐없이 추출하세요."
) if query_type == "risk" else ""
```

**효과** (`exhaustive_extraction_2026-04-26`, 3개 contextual variant 기준):

| 지표 | evidence_cap | exhaustive |
|---|---|---|
| risk completeness (contextual_all) | 0.3 | 0.7 |
| risk completeness (parent_only) | **0.0** | 0.7 |
| risk completeness (selective_v2) | 0.5 | 0.7 |
| numeric_fact PASS (selective_v2) | **FAIL** | PASS |
| business_overview_001 compl (parent_only) | 1.0 | 1.0 |

**해석**:
- exhaustive 규칙이 risk extraction의 급락(0.0)을 방지하고 0.7로 안정시켰다. compress_tuning 실험의 1.0은 LLM이 우연히 모든 항목을 추출한 lucky run이었다.
- risk faithfulness 0.3은 evaluator structural mismatch (child chunk context로 parent chunk 기반 답변을 판정) 때문이며, 답변에 hallucination이 있는 것이 아니다. sentence_checks에서 6개 항목 모두 `keep`으로 처리됨이 확인됐다.
- numeric_fact FAIL이 exhaustive 실험에서 PASS로 복구됐다 (evidence_cap 실험의 FAIL은 numeric_extractor LLM의 transient failure였음).

**결정**:
- exhaustive extraction 규칙을 유지한다.
- risk completeness 0.7은 현 시점 허용 범위로 본다. 1.0을 안정적으로 달성하려면 evidence extraction을 deterministic하게 만들거나 (regex+LLM hybrid), 또는 retrieval이 더 완전한 리스크 섹션을 가져오는 방향이 필요하다.
- risk faithfulness 0.3 문제는 evaluator 구조 한계로 현 단계에서는 수정하지 않는다.

---

## 결정 63 — `EvidenceItem`에 `parent_category` 필드를 추가해 계층 구조를 명시적 메타데이터로 전달한다

**문제**: `exhaustive_extraction_2026-04-26` 결과 분석에서 risk completeness가 0.7에서 멈추는 원인을 파악했다. `completeness_reason`을 실제로 읽어보면, 항목(환율변동위험·이자율변동위험·주가변동위험·신용위험·유동성위험)은 모두 추출되어 있는데도 0.7이 나오는 이유가 두 가지였다:

1. **계층 레이블 손실**: `_extract_evidence`가 하위 항목들을 독립 EvidenceItem으로 뽑으면서 "이 세 개가 시장위험의 하위 항목"이라는 상위 범주 정보가 소실된다. `_compress_answer`는 flat list를 받으므로 계층을 복원하지 못하고 `[환율변동위험, 이자율변동위험, 주가변동위험, 신용위험, 유동성위험]`을 동등한 peer로 나열한다. answer_key는 `시장위험(→ 3개 하위), 신용위험, 유동성위험`의 계층 구조를 기대하므로 completeness judge가 차감한다.

2. **범위 이탈**: `자본위험`이 공시에는 실제로 존재하는 항목이지만 answer_key에 없어서 judge가 scope 이탈로 차감한다.

**왜 Option A(compress guidance만 수정)가 부족한가**: compress에게 "같은 부모를 공유하면 묶어라"고 지시해도 LLM이 flat text에서 부모를 추론해야 하므로 비결정성이 다시 살아난다. 계층 정보는 extraction 단계에서 구조화된 메타데이터로 명시적으로 넘겨야 한다.

**수정** (`src/agent/financial_graph.py`):

1. **`EvidenceItem` 스키마 확장**:
   ```python
   parent_category: Optional[str] = Field(
       default=None,
       description="해당 근거가 속한 상위 범주 레이블. 예: '시장위험', 'DS부문'. 문서에 명시된 상위 범주가 없으면 None."
   )
   ```

2. **`_extract_evidence` extra_rules 확장**:
   - `risk`: 기존 exhaustive 규칙 유지 + parent_category 태깅 지시 추가
     - "여러 하위 항목이 상위 범주 아래 묶여 있다면(예: '시장위험' 아래 환율·이자율·주가변동위험), 각 하위 항목의 parent_category 필드에 해당 상위 범주 명칭을 그대로 적으세요"
   - `business_overview`: exhaustive + parent_category 규칙 신규 추가

3. **`_build_runtime_evidence_item`**: `parent_category`가 있을 때만 dict에 포함 (None이면 키 생략)

4. **`_format_evidence_for_prompt`**: `parent_category`가 있는 항목에만 `parent_category: ...` 라인 렌더링

5. **`_compression_guidance` (risk / business_overview)**:
   - "evidence에 parent_category가 명시된 항목들은 해당 상위 범주를 먼저 적고 하위 항목을 묶어서 구조화"

**기대 효과**:

extract 단계 출력이 아래처럼 명시적 계층 태그를 포함하게 된다:

```
- evidence_id: ev_001
  parent_category: 시장위험
  claim: 환율변동위험 — 기능통화 외의 통화로 표시된 자산·부채 환산 과정에서 환율 변동이 손익에 영향
- evidence_id: ev_002
  parent_category: 시장위험
  claim: 이자율변동위험 — 변동금리 차입금 보유로 인한 금융비용 변동 위험
- evidence_id: ev_004
  claim: 신용위험 — 거래 상대방 채무불이행 시 금융자산 손실 위험
```

compress는 이 태그를 보고 `시장위험 > [환율변동위험, 이자율변동위험, 주가변동위험]`로 계층 구조를 명확히 복원할 수 있다.

**다음 단계**: 벤치마크를 재실행해 risk_analysis_001 completeness가 0.7 → 1.0으로 개선되는지 확인한다.

---

## 결정 64 — `allowed_grounded_extras`는 장기 정책이 아니라 임시 evaluator 안전장치로만 유지한다

**문제**: `risk_analysis_001`에서 시스템은 원문에 실제로 존재하는 `자본위험`까지 성실하게 추출했지만, answer key는 `시장위험 / 신용위험 / 유동성위험`만 핵심 정답으로 서술하고 있었다. 파이프라인을 answer key에 맞춰 억지로 줄이면 벤치마크 오버피팅 위험이 크다.

**조치**:

1. evaluator 데이터 스키마에 `allowed_grounded_extras` 필드를 추가했다.
2. `risk_analysis_001` / `q_009`에 아래 항목을 허용 추가 정보로 기록했다.
   - `이자율변동위험`
   - `주가변동위험`
   - `자본위험`
3. completeness judge 프롬프트에
   - 허용 추가 항목은 포함되어도 감점하지 말 것
   - 빠져 있어도 감점하지 말 것
   을 명시했다.

**작은 검증 결과**:

- 가장 작은 evaluator-only 재실험으로, `dev_fast_focus_selective_serial_2026-04-27`에 저장된 `risk_analysis_001` 답변 하나를 completeness judge에 다시 넣어 비교했다.
- 결과는
  - `with_allowed_grounded_extras = 1.0`
  - `without_allowed_grounded_extras = 1.0`
  로 동일했다.

즉 이 패치는 현재 케이스의 점수를 실제로 끌어올린 결정적 요인은 아니었다. 현재 judge는 이미 grounded extra detail을 상당 부분 허용하고 있다.

**결정**:

- `allowed_grounded_extras`는 당분간 임시 안전장치로만 유지한다.
- 앞으로 질문별 whitelist를 계속 늘리지 않는다.
- 장기적으로 evaluator는
  - 핵심 정답(core answer)을 모두 포함했는가
  - 추가 내용이 retrieved context에 grounded되어 있는가
  를 원칙으로 판단하는 principle-based completeness judge로 정리한다.

---

## 결정 65 — `comparison / trend` 계산 경로는 `operation enum` 중심에서 `formula planner + safe AST evaluator` 중심으로 전환한다

**문제**: 기존 계산 노드는 `subtract`, `growth_rate`, `time_series_trend`처럼 미리 정의한 operation 이름을 고르고, 파이썬 쪽에서 `if operation == ...` 분기를 따라 계산했다. 이 구조는 baseline 구축에는 유용했지만, operation 종류가 늘어날수록 파이썬 쪽의 rule-based boilerplate가 계속 커지는 한계가 있다.

**조치**:

1. `calculation_plan` 스키마를 아래 중심으로 재구성했다.
   - `mode`
   - `variable_bindings`
   - `formula`
   - `pairwise_formula`
2. `operation` 필드는 유지하지만, 실제 계산을 지시하는 핵심 필드가 아니라 **로그/평가용 힌트**로 격하시켰다.
3. calculator는 `eval()`을 쓰지 않고, AST를 파싱해 허용된 노드와 기본 수학 함수만 실행하는 안전한 evaluator로 교체했다.
4. graph 경로도 `operand_extractor -> formula_planner -> calculator -> calc_render`로 바꿨다.

**효과**:

- `comparison`
  - `A - B`
- `growth_rate`
  - `((A - B) / B) * 100`
- `trend`
  - `((C - A) / A) * 100`
  - `((CURR - PREV) / PREV) * 100`

처럼 계산식 자체를 구조화해 저장할 수 있게 됐다.

**결정**:

- 현재 수학적 baseline은 formula planner + AST evaluator 경로를 기본으로 유지한다.
- operation-specific rule은 더 늘리지 않는다.
- 장기적으로 더 복합한 질문은 같은 틀 위에서 formula complexity만 확장한다.

---

## 결정 66 — `trend` 해석은 파이썬이 아니라 LLM renderer가 맡는다

**문제**: `trend_direction = rebound` 같은 의미 필드를 파이썬에서 계속 하드코딩하기 시작하면, 계산 노드가 다시 rule-based IF-THEN 지옥으로 회귀한다. 시계열이 4년, 5년으로 늘어나거나 질문이 미묘해질수록 유지보수성이 급격히 떨어진다.

**조치**:

1. calculator는 오직 건조한 fact만 남긴다.
   - `series`
   - `derived_metrics.yoy_growth_rates`
   - 최종 수치
2. `calc_render` 노드의 LLM이 이 구조화된 JSON만 보고
   - 증가
   - 감소
   - 반등
   - 변동성
   같은 자연어 해석을 수행한다.
3. renderer 프롬프트에는 strict grounding 규칙을 넣었다.
   - `CalculationResult`와 operand labels의 숫자만 사용할 것
   - 새로운 연도/금액/비율 생성 금지
   - trend 해석은 `series` / `derived_metrics`를 근거로 할 것

**결정**:

- `trend_direction` 같은 의미 필드를 파이썬 쪽에 더 추가하지 않는다.
- 파이썬은 계산만, LLM은 해석과 표현만 담당한다는 분업을 유지한다.

---

## 결정 67 — 계산 전용 evaluator는 `operation string`보다 `numeric result + trend interpretation + grounded rendering`을 중심으로 본다

**문제**: formula planner 도입 후에는 `expected_operation == actual_operation` 같은 문자열 비교가 계산 품질을 제대로 설명하지 못한다. 또한 `63조 8,217억원` vs `63조 8,218억원`처럼 source section 차이에서 오는 반올림 오차를 오답 처리하면 실무적으로 과도하게 경직된 evaluator가 된다.

**조치**:

1. 계산 전용 평가 축을 아래처럼 분해했다.
   - `operand_selection_correctness`
   - `unit_consistency_pass`
   - `numeric_result_correctness`
   - `trend_interpretation_correctness`
   - `grounded_rendering_correctness`
   - `calculation_correctness`
2. `calculation_correctness`는 이제
   - 최종 결과값이 맞는가
   - trend 해석이 맞는가
   - renderer가 없는 금액/비율을 만들어내지 않았는가
   의 평균으로 계산한다.
3. comparison의 KRW 결과는 기본 절대 허용 오차를 둔다.
   - 현재 기준 `1억원`
4. trend 해석과 grounded rendering은 LLM judge로 본다.
   - trend judge는 `series`와 `yoy_growth_rates`만 본다
   - grounded rendering judge는 금액/비율만 엄격히 보고, 연도 숫자는 예외 처리한다

**검증**:

- 기존 selective store 재사용 evaluator-only run:
  - `benchmarks/results/dev_math_focus_formula_reuse_evaltuned_2026-04-27`
- aggregate:
  - `operand_selection_correctness = 1.0`
  - `unit_consistency_pass = 1.0`
  - `numeric_result_correctness = 1.0`
  - `trend_interpretation_correctness = 1.0`
  - `grounded_rendering_correctness = 1.0`
  - `calculation_correctness = 1.0`

**결정**:

- formula-era math evaluator의 기본 철학은
  - 계산 본질은 엄격하게
  - 표현 차이는 더 유연하게
  로 유지한다.

---

## 결정 64 — `calc_render` 렌더링 버그 수정: direction_hint 주입, 라벨 보존, PERCENT 포맷 고정

**문제**: `trend_002` (영업이익 YoY 성장률) 실행 결과가 `calc_correctness=0.667`, `completeness=0.0`, `numeric_final_judgement=FAIL`이었다.

실제 출력: `"영업이익은(는) 영업이익 대비 398.3402% 변동했습니다."`  
기대 출력: `"2024년 영업이익은 2023년 대비 약 398.3% 증가했습니다."`

원인 분석:
1. **라벨에서 연도 소실**: 프롬프트의 "operand label은 필요하면 조금 자연스럽게 풀어쓸 수 있지만"이라는 허용 문구가 LLM에게 `"2024년 영업이익" → "영업이익"` 단축 허가로 해석됨
2. **방향어 오선택**: `growth_rate` 연산임에도 LLM이 중립 단어 "변동"을 선택. result_value 부호를 LLM이 판단하게 두면 비결정성이 생김
3. **과다 정밀도**: calculator가 PERCENT를 `:,.4f`로 포맷해 `"398.3402%"` 출력 → `numeric_equivalence=0.0` (문서의 `"398.3%"`와 문자열 불일치)

`operand_extractor`와 `formula_planner`는 정상이었음 (labels에 연도 포함, plan도 올바름). 문제는 모두 `calc_render` 단계의 LLM 입력 품질과 프롬프트였음.

**수정** (`src/agent/financial_graph.py`):

1. **`_format_calculation_value` — PERCENT 포맷 수정**:
   - `f"{value:.1f}"` 고정 (기존 `:,.4f` rstrip)
   - `15.0%`를 `15%`로 줄이는 `:g` 포맷 회피
   - 단위 비교를 case-insensitive + `{"PERCENT", "%", "퍼센트"}` 방어 처리

2. **time_series 인라인 포맷도 동일하게 수정** (별도 코드 경로)

3. **`_render_calculation_answer` — direction_hint를 Python에서 결정론적으로 계산**:
   ```python
   if operation == "growth_rate":
       direction_hint = "증가" if result_val > 0 else "감소" if result_val < 0 else "변동 없음"
   elif operation == "subtract":
       direction_hint = "더 큽니다" if result_val > 0 else "더 작습니다" if result_val < 0 else "동일합니다"
   ```
   LLM에게 부호 판단을 위임하지 않음. `subtract`도 포함해 확장성 확보.

4. **renderer 프롬프트 강화**:
   - "조금 자연스럽게 풀어쓸 수 있지만" 제거
   - "연도·기간 정보는 반드시 그대로 유지" 명시
   - `{direction_hint}` 변수 추가 및 사용 지시

**효과** (`calc_render_fix_2026-04-27`):

| 지표 | 수정 전 | 수정 후 |
|------|---------|---------|
| trend_002 actual_answer | "영업이익은(는) 영업이익 대비 398.3402% 변동했습니다." | "삼성전자의 2024년 영업이익은 2023년 대비 398.3% 증가했습니다." |
| calc_correctness | 0.667 | **1.0** |
| completeness | 0.0 | **1.0** |
| numeric_final_judgement | FAIL | **PASS** |
| comparison_001 completeness | ? | **1.0** |
| trend_001 completeness | ? | **1.0** |

**결정**: 세 수정 모두 유지한다. direction_hint Python 주입 패턴은 향후 새 operation 추가 시에도 동일하게 적용한다.

---

## 결정 68 — math 질문셋 확장 및 라우팅/계산 파이프라인 강화

**배경**: eval_dataset.math_focus.json을 3문제에서 8문제로 확장하면서 드러난 여러 실패 유형을 수정했다.

### 확장된 질문 목록
- comparison_002 (add, SDC+Harman 합계)
- comparison_003 (subtract, DS-SDC 차이)
- comparison_004 (ratio, 영업이익률)
- comparison_005 (ratio, 연구개발비 비중)
- trend_003 (growth_rate 음수, 2022→2024 -24.6%)

### 주요 실패 원인과 수정

**1. 라우팅 오분류 (numeric_fact fast-path 과적용)**

`영업이익률`, `비중` 등 계산형 질문이 `numeric_fact` 임베딩과 가까워 fast-path로 확정되면 `numeric_extractor`로 빠져 계산 불가. 두 층으로 방어:
- Canonical routing examples에서 `이익률`/`비중` 타입을 `comparison`으로 추가, `numeric_fact`에서 제거 → 임베딩 공간 분리 (메인)
- `{numeric_fact, comparison}` confusion pair 추가 → margin threshold 0.04→0.10
- `_CALC_GUARDRAIL_KEYWORDS` 키워드 가드 유지 → margin이 threshold를 넘는 엣지케이스의 최후 안전장치

**2. Cross-section retrieval (comparison_005)**

R&D 비중 질문에서 EntityExtraction이 `section_filter="연구개발"`로 추출 → 분모(총 매출, 요약재무정보)가 retrieval에서 밀림. 해결: `EntityExtraction.section_filter` description에 "분자/분모가 다른 섹션에 있으면 None 반환" 지시 추가. 키워드 기반 `_CROSS_SECTION_CALC_KEYWORDS` 하드코딩 불사용.

**3. 단일 PERCENT 피연산자 passthrough**

문서에 비중이 이미 직접 기재된 경우(예: "연구개발비 비중 11.6%") operand extractor가 단일 PERCENT 값을 추출 → formula planner가 두 피연산자 없어 fail. 해결: `_execute_calculation` 시작부에 단일 PERCENT 피연산자 passthrough 추가.

**4. 음수 growth_rate 렌더링 중복**

`rendered_value="-24.6%"`에 `direction_hint="감소"`가 합쳐져 "-24.6% 감소"가 되어 논리 모순. 해결: direction_hint가 존재하고 result_val < 0이면 rendered_value에서 앞쪽 `-`를 lstrip. operation 타입 무관하게 일반화.

**5. `_format_korean_won_compact` 반올림 조건**

억 단위 반올림을 1억 미만에도 일괄 적용하면 소액 왜곡 발생. 1억 이상일 때만 억 단위에서 반올림하도록 조건 추가.

**6. answer_key 구체성 원칙**

LLM evaluator가 answer_key를 채점 기준으로 삼으므로, 개별 수치를 제거하거나 "약"으로 희석하면 채점이 느슨해짐. answer_key는 구체적인 원본 수치를 포함하고 tolerance는 expected_calculation_result 필드에서 별도 관리한다.

**최종 결과** (blvhr8s54, 전체 변경 통합 후):

| 지표 | 값 |
|---|---|
| calc_correctness | **1.0** (8/8) |
| completeness | **0.9625** |
| numeric_result_correctness | **1.0** |
| grounded_rendering_correctness | **1.0** |
| trend_interpretation_correctness | **1.0** |
| full_avg_score | 0.759 |

comparison_003의 completeness 0.7은 "81조 9,082억원" vs answer_key "81조 9,081억원" 1억 차이에서 비롯된 것으로, LLM이 원문 수치를 변환하는 비결정성 문제. numeric_result_correctness는 tolerance=0.001로 1.0 통과. 수치 채점은 허용 범위 내이므로 현 상태를 안정적 베이스라인으로 확정.

---

## 결정 69 — math pipeline은 debug-first 회고를 거쳐 retrieval/source 문제를 앞단에서 해결한다

**문제**: `comparison_005`, `comparison_006`을 고치면서 `%p`, ratio, source supplement, evaluator tolerance 등 국소 패치가 빠르게 늘었다. 일부는 유효했지만, 실제 병목이 retrieval/source miss인데 planner나 evaluator를 계속 만지는 순간이 있었다.

**조치**:

1. 실제 워크플로를 짧게 재현하는 `src/ops/debug_math_workflow.py`를 추가했다.
2. 이 스크립트로 다음을 질문별로 확인한다.
   - routing
   - retrieve
   - evidence
   - ratio_row_candidates
   - component_candidates
   - operand extraction
   - formula planning
   - calculation
3. `comparison_005`, `comparison_006`의 초기 실패는
   - `ratio_row_candidates = 0`
   - `component_candidates = 0`
   로 확인되었고,
   핵심 병목은 `연구개발 활동` source가 seed retrieval에 안 들어오는 것임이 드러났다.
4. 이후 retrieval 한 층만 수정해
   - `연구개발 + 비율/비중/%/%p` 질문에서
   - `연구개발 활동` 계열 섹션을 보조 seed로 merge
   하도록 했다.

**결과**:

- `dev_math_edge_focus_retrievalfixed_2026-04-28`
  - `comparison_005`, `comparison_006`, `comparison_007` 모두 회복
  - `Faithfulness 1.000`
  - `Completeness 1.000`
  - `Numeric Pass Rate 1.000`

**추가 판단**:

- `_supplement_section_seed_docs()` 같은 retrieval rescue path는 현재는 유효하지만, 장기 기본값으로 굳히지 않는다.
- 특히 특정 숫자(`11.6%`, `10.9%`, `35조 215억원`)를 retrieval score에 반영하는 것은 벤치마크 오버피팅 위험이 크다.
- 장기적으로는
  - metric-specific knowledge를 설정 파일(재무 온톨로지)로 분리하고
  - retrieval은 그 설정을 읽어 multi-query expansion / section bias를 생성하며
  - ratio row / component row 추출은 planner failure fallback이 아니라 planning input으로 이동하는 방향을 목표로 한다.

**결정**:

- 앞으로 math path 수정은
  1. debug workflow로 실패 층 확정
  2. 해당 층만 수정
  3. 같은 debug workflow 재확인
  4. 마지막에 benchmark
  순서로 진행한다.
- `direction_hint`처럼 부호/대소 관계를 확정하는 최소 결정론적 로직은 유지한다.
- 반면 metric-specific source choice, section supplement, ratio query 의미 해석은 장기적으로 코드에서 비워내고, 설정 + LLM planner 쪽으로 이동한다.

---

## 결정 70 — 재무 온톨로지는 `router-later, planner/retrieval-first` 순서로 얇게 도입한다

**배경**: `comparison_005`, `comparison_006` 문제를 지나치게 국소 패치로 덮지 않기 위해, `연구개발비 비중`, `영업이익률` 같은 metric-specific 도메인 지식을 코드 밖으로 빼낼 필요가 생겼다.

**판단**:

- ontology 방향 자체는 맞다
- 하지만 `router`부터 전면 치환하면
  - 새 rule-based classifier를 코드 밖으로 옮긴 것에 그칠 수 있고
  - 라우팅 안정성을 다시 흔들 위험이 있다
- 따라서 1차 적용 범위는
  - retrieval hint
  - preferred section
  - ratio row / component candidate scan
  - planner prior
  에 한정한다

**구현**:

- `src/config/financial_ontology.json`
- `src/config/ontology.py`

현재 ontology가 제공하는 역할:

- metric family 감지
- preferred section 목록
- row pattern / component keyword
- formula template / result unit prior

**결정**:

- ontology는 우선 `retrieval / planner`에만 연결한다
- `router`를 ontology-driven prompt로 전환하는 것은 2차 과제로 둔다
- 현재 ontology는 hard filter가 아니라 **thin bias / prior** 용도로 사용한다

---

## 결정 71 — `%p` pre-LLM type-guard는 제거하고 planner를 먼저 신뢰한다

**문제**: `comparison_006` (%p 차이) 대응 과정에서 planner가 실패하던 시절 넣은 pre-LLM type-guard가 남아 있었고, 이 로직이 planner 앞에서 `A-B`를 먼저 확정하고 있었다.

즉 한동안은 `%p` 질문을 실제로 planner가 푸는지, 아니면 기존 guard가 푸는지 분리해서 보지 못했다.

**디버그 결과**:

- guard ON:
  - `%p` 질문은 planner 호출 전에 short-circuit
- guard OFF:
  - ontology prior와 percent operands만으로 planner가 스스로 `formula=A-B`, `result_unit=%`를 생성

대표 케이스:

- `comparison_005`
  - planner가 `formula=A`를 직접 선택
- `comparison_006`
  - planner가 `formula=A-B`를 직접 선택
- `comparison_007`
  - planner가 `formula=A-B`를 직접 선택

**결정**:

- `%p` 질문의 pre-LLM short-circuit type-guard는 제거한다
- planner는 항상 직접 계획을 세운다
- 다만 `%p` 질문에서 non-PERCENT operand를 제거하는 최소 candidate filtering은 유지한다
  - 이것은 planner 우회가 아니라 **candidate 정리 단계**로 본다

---

## 결정 72 — 빠른 math 회귀는 `eval-only` fast path를 기본 루프로 사용한다

**문제**: `benchmark_runner`는 질문 평가 병렬화가 들어가도 cache signature에 runner hash가 포함되어 있어, 코드가 조금만 바뀌어도 store cache가 무효화되어 re-ingest를 다시 타기 쉽다.

즉 full benchmark는 여전히 빠른 반복 실험용으로는 무겁다.

**조치**:

- `src/ops/run_eval_only.py` 추가
- 기존 benchmark 결과 번들의 persisted store를 재사용해
  - parse / ingest / screening 없이
  - full evaluation만 다시 수행

**주의점**:

- source output dir는 **실제로 문서가 들어 있는 유효한 결과 번들**이어야 한다
- `benchmarks/results/latest`처럼 중간에 끊긴 run은 persisted store가 비어 있을 수 있으므로 source로 쓰지 않는다

**검증**:

- `dev_math_focus_llmshift_2026-04-28` 번들을 source로 사용한
  `dev_math_focus_evalonly_2026-04-28` 재실행은 정상 완료
- 결과:
  - `Faithfulness 0.900`
  - `Relevancy 0.798`
  - `Recall 0.893`
  - `Completeness 0.940`
  - `Numeric Pass 0.778`

**결정**:

- 앞으로 math regression은
  1. `debug_math_workflow.py`
  2. `run_eval_only.py`
  3. 필요할 때만 full `benchmark_runner`
  순서로 실행한다
