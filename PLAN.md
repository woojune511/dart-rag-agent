# 실행 계획

이 문서는 다음 스프린트의 우선순위와 성공 조건을 정리한 계획서다.

## 현재 기준선

현재 기본 baseline:

- `chunk_size = 2500`
- `chunk_overlap = 320`
- `ingest_mode = contextual_all`
- retrieval = dense + BM25 + RRF
- reasoning = evidence-first

현재까지 확인된 사실:

- 삼성전자 기준으로 `contextual_parent_only_2500_320`가 screening을 통과한 적이 있다
- `plain`은 risk retrieval miss가 반복됐다
- `contextual_selective_v2`는 business overview miss 가능성이 남아 있다
- `contextual_parent_hybrid`는 품질은 보완할 수 있지만 비용 이점이 약할 수 있다
- 3기업을 한 번에 도는 monolithic run은 timeout과 비용 리스크가 커서 기본 루프로 부적합하다

추가로 확인된 평가 한계:

- 기존 `ground_truth` 한 줄만으로는 도메인 비전문가가 정답 타당성을 검수하기 어렵다
- retrieval 지표보다 answer-level 지표의 신뢰도를 설명하기 어려웠다

## 이번 스프린트 목표

이번 스프린트는 운영 기본값을 바꾸는 단계가 아니다.  
대신 **삼성전자 / SK하이닉스 / NAVER 3개 기업에서 screening quality floor를 재현하는 후보를 확인하고, 그 결과로 기본값 후보를 선택할 수 있게 만드는 것**이 목표다.

기본 운영 방식:

- 평소에는 `benchmarks/profiles/dev_fast.json`으로 단일 기업 + screening only
- shortlist 검증 때만 `benchmarks/profiles/release_generalization.json`으로 3기업 run
- release run도 회사별 job으로 분리 실행하고 partial summary를 허용

핵심 질문:

- `contextual_parent_only`가 삼성전자 외 기업에서도 통과하는가
- `contextual_selective_v2`가 특정 기업에서 반복적으로 실패하는 질문 유형이 있는가
- 같은 후보가 최소 2개 기업에서 통과하는가
- baseline 대비 API calls / ingest 시간이 얼마나 줄어드는가
- reviewer artifact만으로 기업별 정답 근거를 추적할 수 있는가

## 우선순위 작업

### 1. 일반화 benchmark matrix 구성

- 대상 기업:
  - `삼성전자`
  - `SK하이닉스`
  - `NAVER`
- 비교 후보:
  - `contextual_all_2500_320`
  - `contextual_parent_only_2500_320`
  - `contextual_parent_hybrid_2500_320`
  - `contextual_selective_v2_2500_320`

목표:

- 기업별 screening 결과와 cross-company aggregate를 함께 남기기
- 후보별 pass count와 비용 절감률을 직접 비교할 수 있게 만들기
- 회사별 개별 실행 결과를 root partial summary로 합칠 수 있게 만들기

### 1-1. Cost-efficient workflow 정착

- `reuse_store`, `reuse_context_cache`, `force_reindex`를 실행 설정으로 명시
- 같은 보고서/동일 청킹 설정 재실행 시 contextual ingest 비용을 다시 쓰지 않게 만들기
- `stores/`와 `context_cache/`를 분리해, store를 다시 만들더라도 API 호출은 재사용할 수 있게 유지
- fast loop에서는 full eval을 기본 비활성화

### 2. 기업별 canonical eval dataset 확장

- 삼성전자 canonical dataset 유지
- `SK하이닉스`, `NAVER`용 canonical dataset 추가
- 각 기업당 최소 8문항 이상 확보
- 형식:
  - `answer_key`
  - `expected_sections`
  - `evidence`
  - `missing_info_policy`

목표:

- 도메인 지식 없이도 질문별 정답 근거를 검수 가능하게 만들기
- 제조업 / 플랫폼 기업 간 섹션 차이를 평가 데이터에 반영하기

### 3. 평가 보강

- screening cutoff는 그대로 유지:
  - `retrieval_hit_drop_threshold = 0.10`
  - `section_match_drop_threshold = 0.15`
- critical category는 `risk / business / numeric`로 본다
- 산출물:
  - 기업별 `results.json`, `summary.csv`, `summary.md`, `review.csv`, `review.md`
  - 전체 `cross_company_summary.csv`, `cross_company_summary.md`
- 승자 선정 우선순위를 문서화:
  1. pass count
  2. critical miss 여부
  3. API calls 감소율
  4. ingest 시간 감소율
  5. full eval의 `faithfulness`, `context_recall`
  6. reviewer artifact 정성 검토

## 측정 항목

### 품질

- `retrieval_hit_at_k`
- `section_match_rate`
- `citation_coverage`
- `contamination_rate`
- reviewer artifact에서 질문별 정답 근거 추적 가능 여부

### 속도 / 비용

- `ingest.elapsed_sec`
- `api_calls`
- `parent_context_calls`
- `child_context_calls`
- `prompt_tokens`
- `output_tokens`

### 정식 평가

- `faithfulness`
- `answer_relevancy`
- `context_recall`

## 성공 조건

아래를 모두 만족하는 기본값 후보 1개 이상 확보:

- 동일 후보가 3개 기업 중 최소 2개 기업에서 screening 통과
- risk/business/numeric 질의에서 `retrieval_hit_at_k == 0` 없음
- contamination 없음
- baseline 대비 다음 중 하나 이상 달성
  - `api_calls` 40% 이상 감소
  - `ingest.elapsed_sec` 30% 이상 감소
- cross-company summary와 reviewer artifact만으로 선택 근거를 설명 가능

## 다음 단계

이번 스프린트의 실제 결과는 다음과 같다.

- `삼성전자`: `contextual_parent_hybrid_2500_320`만 통과
- `SK하이닉스`: `contextual_all_2500_320`만 통과
- `NAVER`: 통과 후보 없음
- 따라서 "같은 후보가 최소 2개 기업에서 통과" 조건은 아직 충족되지 않았다

지금 기준 다음 우선순위는 아래다.

1. NAVER 문서의 `section_path` 이상 징후를 parser / section extraction 수준에서 먼저 수정
2. 숫자 질의 section alias를 `연결재무제표`, `연결재무제표 주석`까지 확장할지 검토
3. "근거를 찾지 못했다" 응답이 과대평가되는 judge / evaluation 로직 보정
4. 그 다음에 generalization benchmark를 재실행
5. 재실행 결과를 기준으로 기본값 후보 shortlist를 다시 확정
