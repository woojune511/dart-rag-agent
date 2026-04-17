# 프로젝트 컨텍스트

## 현재 상태

현재 시스템은 다음 경로가 실제로 동작합니다.

- DART API로 사업보고서 수집
- DART XML 구조 파싱
- 구조 기반 청킹 + parent-child metadata 생성
- ChromaDB + BM25 + RRF hybrid retrieval
- evidence-first reasoning
- FastAPI / Streamlit 인터페이스
- benchmark runner 기반 자동 실험

기본 설정은 현재 다음과 같습니다.

- Embedding: `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2`
- Collection: `dart_reports_v2`
- Chunk size / overlap: `2500 / 320`
- Baseline ingest mode: `contextual_all`

## 최근 반영 사항

- benchmark runner에 2단계 평가 구조 반영
  - screening
  - full evaluation
- ingest mode 비교 지원
  - `plain`
  - `contextual_all`
  - `contextual_parent_only`
  - `contextual_selective`
- screening 실험 병렬 실행 지원
  - `screening.parallel_experiments`
- benchmark 질문셋 / 평가셋 JSON 추적 가능하도록 `.gitignore` 범위 축소
- `eval_dataset.template.json`을 실제 삼성전자 2024 사업보고서 기준으로 보강
- `dev_fast` / `release_generalization` 실행 프로파일 추가
- 회사별 job 실행 + partial summary 지원
- `Hybrid Cache` 도입
  - `stores/...` 재사용
  - `context_cache/...` 재사용
- NAVER `section_path` heading level 정규화 반영
- numeric section alias 확장
  - `연결재무제표`
  - `연결재무제표 주석`
- full abstention 패턴만 answerable query 페널티로 취급하도록 평가 보정
- `release_generalization`을 회사별 job으로 재실행해 `v4_generalization_fix_2026-04-17` 완료
- cross-company summary 생성까지 확인

## 최신 benchmark 메모

기준 문서:

- 삼성전자 2024 사업보고서
- 접수번호 `20250311001085`

현재 결과 요약:

- `contextual_all_2500_320`
  - screening 통과
  - `Hit@k 1.000`, `Section 0.250`
  - `Faithfulness 0.400`, `Relevancy 0.651`, `Recall 0.500`
- `contextual_parent_only_2500_320`
  - 빠르지만 numeric question에서 `Hit@k` 하락
- `contextual_selective_2500_320`
  - 비용 절감 폭이 작고 business overview retrieval miss 발생
- `plain_2500_320`
  - 매우 빠르지만 risk query retrieval miss
- `contextual_1500_200`
  - 가장 느리고 business overview miss 발생

### Fast profile 검증

기준 run:

- `benchmarks/results/dev_fast_cache_check_2026-04-17`

검증 내용:

- `dev_fast`로 삼성전자 1회사 screening-only 2회 연속 실행
- 1차 run 약 `13분 16초`
- 2차 run 약 `5분 27초`
- 2차 run에서 모든 후보가:
  - `cache.cache_hit = true`
  - `cache.cache_level = store`
  - `ingest.api_calls = 0`
  - `ingest.elapsed_sec = 0.0`

해석:

- 동일 설정 재실행 시 contextual ingest API 비용은 재발생하지 않음
- 반복 실험의 주 병목은 이제 ingest보다 query / screening 단계에 가까움

### v4 generalization 완료

기준 run:

- `benchmarks/results/v4_generalization_fix_2026-04-17`

완료 상태:

- `run_status = completed`
- 완료 기업:
  - `삼성전자`
  - `SK하이닉스`
  - `NAVER`

핵심 결과:

- 공통 screening 통과 후보 없음
- `contextual_all_2500_320`
  - 가장 안정적인 baseline
  - 평균 full eval:
    - `faithfulness 0.453`
    - `context recall 0.589`
- `contextual_parent_only_2500_320`
  - 비용 절감은 가장 크지만
  - numeric / risk / R&D 질문에서 abstention 반복
- `contextual_parent_hybrid_2500_320`
  - 일부 품질 보완은 있으나 baseline보다 비싼 경우가 있음
- `contextual_selective_v2_2500_320`
  - 비용 절감은 크지만 business overview / risk miss가 남음

## 현재 해석

지금 병목은 parser가 아니라 contextual ingest입니다.  
문제는 이미 “병렬화가 필요한가”를 넘어서, **저비용 후보의 query-stage 실패를 어떻게 줄일 것인가**로 이동했습니다.

현재 가장 유력한 다음 실험 축:

- query-stage abstention 완화
  - numeric / risk / R&D 질문에서 근거가 일부 있어도 완전 abstain으로 흐르는 패턴 점검
- NAVER business overview retrieval 개선
  - `I. 회사의 개요` 편중을 줄이고 실제 사업 설명 section 우선순위 재검토
- missing-information 판정 안정화
  - hallucination 없이 명시적 부재 응답을 유도하는 prompt / 평가 보정
- fast loop 추가 최적화
  - smoke 질문 수와 screening slice 재조정

## 현재 작업 트리에서 중요 포인트

- benchmark JSON은 이제 git 추적 가능
- 로컬 전용 파일은 계속 ignore
  - `benchmarks/experiment_matrix.local.json`
  - `benchmarks/results/**/stores/`
  - `mlflow.db`

## 다음 세션 우선순위

1. `contextual_all` baseline을 유지한 채 query-stage abstention 원인 분석
2. NAVER business overview miss를 만드는 retrieval / rerank 패턴 점검
3. missing-information hallucination 억제 보강
4. 그 다음에야 `parent_only` / `selective_v2` 재설계 여부 판단
