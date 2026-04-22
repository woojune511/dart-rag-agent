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

현재는 시스템 전반을 다시 정렬하기 위해, 다기업 generalization보다 **단일 문서 Golden Dataset과 evaluator 확정**을 먼저 하기로 했다.
기준 문서는 `삼성전자 2024 사업보고서`다.

현재 single-document baseline 자산:

- `docs/single_document_eval_strategy.md`
- `docs/golden_dataset_schema.md`
- `benchmarks/golden/samsung_2024_v1.json`
- `benchmarks/profiles/single_document_dev.json`

현재 상태:

- Golden Dataset `v1 draft` 20문항 생성 완료
- `src/ops/evaluator.py`는 기존 canonical schema와 Golden Dataset schema v1을 모두 읽도록 확장 완료
- `single_document_dev` profile에서 삼성전자 2024 기준 `20문항`이 선택되는 것 확인
- 다음 우선순위는 이 20문항을 `draft -> verified`로 수동 검수하는 것

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
- `compress` / `validate` typed output 도입
  - `selected_claim_ids`
  - `draft_points`
  - `kept_claim_ids`
  - `dropped_claim_ids`
  - `unsupported_sentences`
  - `sentence_checks`
- sentence-level validator 후처리 보강
  - `drop_overextended`
  - `drop_unsupported`
  - `drop_redundant`
  를 실제 pruning으로 연결

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

판단:

- 이 케이스는 generation 문제가 아니라 evaluator limitation으로 본다.
- 그래서 `numeric_fact`는 generic `faithfulness` 하나로 해석하지 않고,
  - `numeric_equivalence`
  - `numeric_grounding`
  - `numeric_retrieval_support`
  - `numeric_final_judgement`
  를 함께 본다.

## typed compression / validation 최신 메모

기준 run:

- `benchmarks/results/dev_fast_cache_check_2026-04-17`
- `benchmarks/results/dev_fulleval_sentence_validator_2026-04-21`
- `benchmarks/results/dev_focus_validator_2026-04-21`

진행 순서:

1. structured evidence를 runtime artifact에 남김
2. `compress -> validate`를 typed output으로 전환
3. `review.csv` / `review.md`에
   - `selected_claim_ids`
   - `draft_points`
   - `kept_claim_ids`
   - `dropped_claim_ids`
   - `unsupported_sentences`
   - `sentence_checks`
   를 기록
4. sentence-level validator를 넣고, 후처리에서 실제 prune verdict를 반영

현재 관찰:

- typed artifact는 의도대로 잘 남는다.
- 하지만 5문항 full eval 기준으로는 validator가 아직 충분히 많이 자르지 못한다.
- `dev_fulleval_sentence_validator_2026-04-21` 기준 `contextual_all` 변화:
  - `faithfulness 0.600 -> 0.540`
  - `relevancy 0.711 -> 0.586`
  - `recall 0.600 -> 0.600`
  - `hit@k 0.800 -> 1.000`
  - `section 0.300 -> 0.325`
  - `citation 0.800 -> 0.867`
- 즉 retrieval / citation 쪽은 좋아졌지만, answer quality는 아직 안정적으로 개선되지 않았다.

focus run 관찰:

- `dev_focus_validator_2026-04-21`에서 `risk_analysis_001`은 실제로 pruning이 발생했다.
- `contextual_all`
  - 도입 문장 하나가 `drop_redundant`
- `contextual_parent_only`
  - 도입 문장 하나가 `drop_unsupported`
  - `dropped_claim_ids = ev_002`

현재 해석:

- validator는 이제 “기록만 하는 단계”는 지났다.
- 하지만 아직 “잘 자르는 validator”까지는 아니다.
- 지금 병목은 validator 강도보다, `business_overview` / `risk`에서 어떤 claim을 같이 선택하느냐에 더 가깝다.

다음 우선순위:

- evidence에 `claim_type` / `topic_key`를 추가
- compression을 top-N이 아니라 group-wise selection으로 변경
- `business_overview`
  - `DX / DS / SDC / Harman` 대표 claim만 선택
- `risk`
  - 상위 taxonomy claim과 세부 risk claim을 동시에 다 넣지 않기

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

## typed compression / validation 반영 메모

반영 범위:

- `src/agent/financial_graph.py`
  - `CompressionOutput`
  - `ValidationOutput`
- `src/ops/evaluator.py`
  - per-question 결과에 claim selection / drop 정보 추가
- `src/ops/benchmark_runner.py`
  - `results.json`, `review.csv`, `review.md`에 새 필드 직렬화

핵심 변화:

- 기존 `compress` / `validate`는 문자열만 주고받는 구조에 가까웠다.
- 현재는 아래 typed output을 남긴다.
  - `selected_claim_ids`
  - `draft_points`
  - `kept_claim_ids`
  - `dropped_claim_ids`
  - `unsupported_sentences`
- 질문 wording 기반 output style 분기는 제거했다.
- 이 변경으로 reviewer artifact에서 “무슨 claim을 썼고, 무엇을 버렸는지”를 직접 추적할 수 있게 됐다.

현재 상태:

- `py_compile` 검증 완료
- 아직 새 typed field를 포함한 full eval 재실행은 하지 않았다.
- 다음 검증은 삼성전자 1회사 `dev_fast_fulleval`을 다시 돌려, review artifact에 새 필드가 실제로 유의미하게 남는지 확인하는 것이다.

## 다음 세션 우선순위

1. 최근 answer-stage rule inventory 정리
   - 유지 / 실험용 / 제거 후보 분류
2. answer generation 구조 재설계
   - evidence compression 중심으로 재정의
   - benchmark-only 최적화와 운영 기본값 분리
3. typed compression / validation 결과 검증
   - `selected_claim_ids`
   - `dropped_claim_ids`
   - `unsupported_sentences`
   가 review artifact에서 실제로 해석 가능한지 확인
4. numeric evaluator 후속 정리
   - aggregate / summary에서 `numeric_final_judgement`를 더 전면에 노출
   - `UNCERTAIN` 버킷 해석 규칙 정교화
5. NAVER business overview retrieval 실패 원인 정리
6. missing-information hallucination 억제 보강
7. 그 다음에 `dev_fast` 기준 재실험
8. 실패 유형이 줄어든 뒤에만 전체 3개사 재벤치마크

## 새 기준선: single-document benchmark lab

다음 단계는 retrieval / generation tweak가 아니다.

먼저 할 일:

1. 삼성전자 2024 사업보고서 1건 기준으로 Golden Dataset 20~30개 구축
2. 질문 taxonomy 확정
   - `single-hop-fact`
   - `multi-hop-comparison`
   - `multi-hop-calculation`
   - `synthesis-abstract`
   - `adversarial-out-of-domain`
3. JSON schema v1 확정
4. evaluator 분리
   - retrieval
   - generation
   - numeric
   - refusal
5. benchmark runner를 single-document 기준으로 먼저 고정

이 판단의 이유:

- 지금은 평균 metric보다 평가 기준 자체를 먼저 고정하는 편이 중요하다.
- multi-company run은 parser 차이, section alias 차이, evaluator 차이가 섞인다.
- local rule을 더 붙이는 것보다 “무엇을 좋은 답으로 볼 것인가”를 단일 문서에서 먼저 고정해야 한다.

참조:

- [single_document_eval_strategy.md](docs/single_document_eval_strategy.md)
