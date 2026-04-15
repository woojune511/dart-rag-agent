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

## 현재 해석

지금 병목은 parser가 아니라 contextual ingest입니다.  
문제는 이미 “병렬화가 필요한가”를 넘어서, **저비용 후보를 어떻게 screening 통과 수준까지 끌어올릴 것인가**로 이동했습니다.

현재 가장 유력한 다음 실험 축:

- `parent_only` 보완
  - 숫자/표 질의만 child-level context 유지
- `selective` 보완
  - selector를 훨씬 더 공격적으로 줄이고 핵심 섹션만 유지
- 평가셋 보강
  - 숫자 질의의 허용 section 범위 재검토

## 현재 작업 트리에서 중요 포인트

- benchmark JSON은 이제 git 추적 가능
- 로컬 전용 파일은 계속 ignore
  - `benchmarks/experiment_matrix.local.json`
  - `benchmarks/results/**/stores/`
  - `mlflow.db`

## 다음 세션 우선순위

1. `parent_only hybrid` 실험안 추가
2. `selective_v2` selector 설계
3. screening 기준과 eval dataset의 섹션 기대치 재검토
4. 다른 기업 1건 추가 검증
