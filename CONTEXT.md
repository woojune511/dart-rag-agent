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
- `v6` / `v7` 삼성전자 single-company full eval로 faithfulness 회복 실험 수행
- structured runtime evidence 기록 확인
- answer generation을 `compression -> validation` 구조로 분리

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

## 최근 반영된 query-stage 개선 (결정 39~42)

v4 benchmark 결과 분석 후 실패 경로를 수정했다.

**A — Evidence 하드 abstain 방지** (`_extract_evidence`):
- `docs[:6]` → `docs[:8]`로 evidence LLM 입력 확대
- `coverage=missing` + docs 존재 시 → deterministic fallback(sparse)으로 전환, 하드 abstain 제거

**B — Analyze 과잉 추론 억제** (`_analyze`):
- `risk` instruction에서 “잠재 영향 설명” 제거
- “확인되지 않습니다” 사용을 질문 전체 abstain 때만으로 제한
- sparse evidence 시 별도 보수적 instruction 적용 (카테고리 생성·추론 금지)

**C — query_type 6종 확장 + 분리 retrieval 레인** (`_classify_query`, `_rerank_docs`, `_retrieve`):
- `qa` catch-all을 `numeric_fact` / `business_overview`로 세분화
- classify 프롬프트: 수치 포함이더라도 사업 구조 파악 목적이면 `business_overview` 판별 기준 추가
- keyword hardcoding 제거 → `_TABLE_PREFERRED_TYPES` / `_PARAGRAPH_PREFERRED_TYPES` 기반
- `_retrieve`에 분리 레인 추가: numeric/trend는 표 우선(단락 최소 2개), overview/risk/qa는 단락 최소 절반 보장

**D — Risk evidence verbatim 제한** (`_extract_evidence`):
- `query_type == “risk”`일 때 `extra_rules` 주입:
  컨텍스트에 없는 리스크 카테고리명(운영위험 등) 생성 금지

**E — Evaluator context 범위 일치** (`evaluator.py`):
- `_compute_faithfulness`: `contexts[:5]` → `contexts[:8]`
- agent 실제 사용 범위(docs[:8])와 맞춰 평가 일관성 확보

검증: 분류 8/8, mock 레인 비율 테스트 통과. v5 full eval 재실험 필요 (결정 42).

## v5 benchmark 결과 요약 (2026-04-20, 삼성전자 contextual_all)

기준: `dev_fast` 프로파일, 7개 질문 (v4 공통 5개 + r_and_d_001 + missing_info_001)

screening (7개 질문 aggregate):
- `contextual_all`: hit@k=0.714, section=0.250
- `contextual_parent_only`: hit@k=0.857, section=0.232  ← screen_pass=True
- `contextual_selective_v2`: hit@k=0.571, section=0.214  ← screen_pass=False

full eval (공통 5개 질문, v4 vs v5 비교):
- context_recall: 0.600 (동일)
- citation_coverage: 0.800 → 0.867 (+0.067)
- faithfulness: 0.660 → 0.380 (-0.280) ← 결정 42 수정 후 재실험 필요
- answer_relevancy: 0.772 → 0.747 (-0.025)

주요 관찰:
- retrieval 수치는 v4와 완전히 동일, latency만 +3~6초 (classify 콜 추가)
- business_overview_001 hit@k=0.0 지속 (회사개요 vs 사업개요 섹션 불일치 문제)
- missing_information_001은 적절하게 abstention (hit=0.0이 정상 동작)

## 현재 작업 트리에서 중요 포인트

- benchmark JSON은 이제 git 추적 가능
- 로컬 전용 파일은 계속 ignore
  - `benchmarks/experiment_matrix.local.json`
  - `benchmarks/results/**/stores/`
  - `mlflow.db`

## v6 / v7 faithfulness 실험 메모

기준 run:

- `benchmarks/results/v6_faithfulness_guard_2026-04-20`
- `benchmarks/results/v7_faithfulness_guard_refine_2026-04-20`

핵심 결과:

- `v5` baseline `contextual_all_2500_320`
  - full faithfulness `0.380`
- `v6`
  - full faithfulness `0.500`
- `v7`
  - full faithfulness `0.600`

세부 해석:

- `v6`와 `v7`에서 `business_overview` 문항은 일부 회복됐다.
- 하지만 `risk_analysis_001`은 다시 `0.0`으로 흔들렸다.
- 즉 최근 rule 추가는 일부 문항을 개선했지만, 다른 문항에서 새 부작용을 만들었다.
- 이건 retrieval 문제가 아니라 answer generation이 benchmark judge에 맞춰 흔들리고 있다는 신호로 본다.

판단:

- 지금은 더 많은 hardcoded rule을 추가할 단계가 아니다.
- 다음 단계는 score를 더 올리는 것이 아니라, answer generation 구조를 더 단순하고 principled하게 재정리하는 것이다.
- 관련 원칙은 [answer_generation_principles.md](docs/answer_generation_principles.md)에 정리했다.

## numeric evaluator 한계와 다음 방향

structured runtime evidence를 붙인 뒤에도 `numeric_fact_001`은 사람이 보기엔 사실상 맞는 답인데 `faithfulness = 0.0`이 반복됐다.

대표 예:

- canonical 표현: `300조 8,709억원`
- actual answer 표현: `300,870,903 백만원`

이 케이스는 generation failure라기보다, **현재 서술형 faithfulness judge가 숫자 동치성을 충분히 인정하지 못하는 evaluator limitation**으로 해석한다.

현재 판단:

- 숫자 질문은 일반 서술형 `faithfulness`와 분리해서 평가해야 한다.
- generation rule을 더 붙이기보다 evaluator를 분리하는 것이 우선이다.
- 다음 단계는 [numeric_evaluation_architecture.md](docs/numeric_evaluation_architecture.md)의 parallel numeric evaluators + resolver 구조를 실제 evaluator에 도입하는 것이다.

## numeric evaluator 구현 및 재검증 메모

반영 범위:

- `src/ops/evaluator.py`
  - `Numeric Extractor`
  - `Numeric Equivalence Checker`
  - `Grounding Judge`
  - `Retrieval Support Check`
  - `Conflict Resolver`
- `src/ops/benchmark_runner.py`
  - `results.json`, `review.csv`, `review.md`에 numeric evaluator 결과 직렬화

재검증 run:

- `benchmarks/results/dev_fast_cache_check_2026-04-17`

핵심 결과:

- `numeric_fact_001`
  - generic `faithfulness = 0.0`
  - `numeric_equivalence = 1.0`
  - `numeric_grounding = 1.0`
  - `numeric_retrieval_support = 1.0`
  - `numeric_final_judgement = PASS`

해석:

- 숫자 질문에서는 generic `faithfulness`가 여전히 false fail을 만들 수 있다.
- 하지만 새 numeric evaluator path는 같은 케이스를 `PASS`로 올바르게 해석했다.
- 따라서 앞으로 `numeric_fact`의 주 판정은 `numeric_final_judgement`를 우선하고, generic `faithfulness`는 보조 지표로 본다.

## 다음 세션 우선순위

1. 최근 answer-stage rule inventory 정리
   - 유지 / 실험용 / 제거 후보 분류
2. answer generation 구조 재설계
   - evidence compression 중심으로 재정의
   - benchmark-only 최적화와 운영 기본값 분리
3. numeric evaluator 후속 정리
   - aggregate / summary에서 `numeric_final_judgement`를 더 전면에 노출
   - `UNCERTAIN` 버킷 해석 규칙 정교화
4. NAVER business overview retrieval 실패 원인 정리
5. missing-information hallucination 억제 보강
6. 그 다음에 `dev_fast` 기준 재실험
7. 실패 유형이 줄어든 뒤에만 전체 3개사 재벤치마크
