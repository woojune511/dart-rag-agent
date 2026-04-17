# Benchmarking Guide

이 문서는 DART 공시 RAG 시스템에서 retrieval 정확도, answer 품질, ingest 시간, API 비용을 함께 비교하기 위한 benchmark 가이드다.

## 목표

현재 benchmark의 목표는 "삼성전자 1건에서 더 싼 후보를 찾기"가 아니라,  
**삼성전자 / SK하이닉스 / NAVER 3개 기업에서 screening quality floor를 재현하는 후보를 찾고 기본값 후보를 선택하는 것**이다.

다만 일상적인 실험 루프는 이제 release-grade full run이 아니라,  
**단일 기업 + screening only 중심의 fast iteration**을 기본으로 한다.

benchmark는 여전히 "모든 후보를 비싼 full evaluation으로 보내는 방식"이 아니라, **screening -> full evaluation의 2단계 구조**로 운영한다.  
다만 이번 단계에서는 "screening을 통과한 후보가 다른 기업에서도 통과하는가"를 핵심 질문으로 둔다.

현재 baseline:

- `contextual_all_2500_320`

기본 실행 프로파일:

- `benchmarks/profiles/dev_fast.json`
- `benchmarks/profiles/release_generalization.json`

기본 평가셋:

- `benchmarks/eval_dataset.canonical.json` for `삼성전자`
- `benchmarks/eval_dataset.skhynix_2024.canonical.json` for `SK하이닉스`
- `benchmarks/eval_dataset.naver_2024.canonical.json` for `NAVER`

이번 스프린트의 질문:

- `contextual_parent_only`가 삼성전자 외 기업에서도 screening을 통과하는가
- `contextual_selective_v2`가 특정 기업에서 반복적으로 무너지는 질문 유형이 있는가
- 어떤 후보가 여러 기업에서 품질 하한선을 넘기면서 API calls / ingest 시간을 줄이는가
- 기본값 후보를 어떤 우선순위로 선택할 것인가

## Ingest Modes

### `plain`

- child chunk 원문만 인덱싱
- LLM contextualization 없음
- API calls 0

### `contextual_all`

- 모든 child chunk에 대해 LLM context 생성
- `context + metadata prefix + child chunk`를 인덱싱
- 현재 품질 baseline

### `contextual_parent_only`

- 같은 `parent_id`를 공유하는 parent section마다 1회만 context 생성
- 각 child chunk는 `parent context + metadata prefix + child chunk`로 인덱싱
- 비용 절감 효과는 크지만 numeric precision 저하 가능성이 있음

### `contextual_parent_hybrid`

- 기본은 `contextual_parent_only`
- 아래 chunk만 child-level context를 추가로 생성
  - `block_type == table`
  - `매출현황`, `재무제표`, `연구개발`, `리스크`, `사업개요`
  - 매우 짧은 chunk
- 목적: parent-only의 비용 절감 효과를 유지하면서 numeric / risk / business miss를 보완

### `contextual_selective`

- retrieval에 취약한 chunk만 context 생성
- v1 규칙 기반 selector

### `contextual_selective_v2`

- 기존 selective보다 더 좁은 selector 사용
- 대표 대상:
  - `사업개요`의 핵심 paragraph
  - `위험관리 및 파생거래` 관련 chunk
  - `매출 및 수주상황` table
  - `연구개발` 핵심 paragraph
  - 짧거나 헤더 의존성이 높은 table
- 목적: 호출 수를 줄이면서 business/risk miss를 줄이기

## 2단계 평가 구조

### 1차 Screening

싸고 빠른 지표만 계산한다.

- `parse.elapsed_sec`
- `ingest.elapsed_sec`
- `api_calls`
- `prompt_tokens`
- `output_tokens`
- `estimated_ingest_cost_usd`
- smoke query latency
- `retrieval_hit_at_k`
- `section_match_rate`
- `citation_coverage`
- `contamination_rate`

추가 분석 필드:

- `failure_examples`
- `selector_reason_counts`
- `parent_context_calls`
- `child_context_calls`

### 2차 Full Evaluation

screening 통과안만 정식 평가로 보낸다.

- `faithfulness`
- `answer_relevancy`
- `context_recall`
- retrieval 계열 지표 재확인

## 실행 프로파일

### `dev_fast`

- 기본 대상: `삼성전자`
- 목적: 새 후보를 빠르게 거르기
- `full_evaluation.enabled = false`
- `eval_mode = single_company_slice`
- smoke + screening만 수행
- 기본적으로 baseline 1개 + 새 후보 1~2개만 돌리는 용도

### `release_generalization`

- 대상: `삼성전자`, `SK하이닉스`, `NAVER`
- 목적: shortlist 후보의 일반화 검증
- `full_evaluation.enabled = true`
- canonical dataset 전체 사용 가능
- 회사별 job으로 분리 실행하고, partial summary를 지원

## 캐시 정책

기본 캐시 정책은 `Hybrid Cache`다.

- `reuse_store = true`
- `reuse_context_cache = true`
- `force_reindex = false`

캐시 키는 아래 조합을 기반으로 한다.

- `company`, `year`, `report_type`, `rcept_no`
- `chunk_size`, `chunk_overlap`, `ingest_mode`
- parser / runner source signature
- selective / hybrid 관련 설정

즉 같은 보고서와 같은 청킹/ingest 설정이면 기존 store와 contextualized 결과를 재사용하고, 파서/설정이 바뀌면 자동으로 무효화된다.

실제 캐시는 두 층으로 나뉜다.

- `stores/...`
  - Chroma / BM25 / parents store 재사용
- `context_cache/...`
  - contextualized text와 metadata를 재사용해서, store를 다시 만들더라도 API 호출 없이 복구

따라서 `reuse_store=false`, `reuse_context_cache=true`인 경우에도 vector store를 깨끗하게 다시 만들면서 contextual ingest 비용은 재사용할 수 있다.

## Canonical Eval Dataset

기존 `ground_truth` 한 줄만으로는 왜 그 답이 맞는지 추적하기 어렵다.  
그래서 기본 평가셋은 이제 **evidence-backed canonical 형식**을 사용한다.

파일:

- `benchmarks/eval_dataset.canonical.json`
- `benchmarks/eval_dataset.skhynix_2024.canonical.json`
- `benchmarks/eval_dataset.naver_2024.canonical.json`

주요 필드:

- `question`
- `answer_key`
- `expected_sections`
- `evidence`
- `missing_info_policy`

핵심 원칙:

- 정답은 요약문(`answer_key`)만 저장하지 않는다.
- 각 질문마다 실제 공시 원문 quote를 `evidence`로 같이 저장한다.
- `context_recall`은 우선 `ground_truth` 문장보다 `evidence.quote` 기준으로 계산한다.
- missing-information 계열 질문은 `missing_info_policy`를 함께 기록해, 어떤 표현이면 합격인지 설명 가능하게 한다.

현재 canonical dataset은 기업별로 8개 이상 문항을 포함하며, 삼성전자 기준 canonical file은 11개 문항을 포함한다.

## 지표 정의

### Speed

- `parse.elapsed_sec`
  - `FinancialParser.process_document()` 실행 시간
- `ingest.elapsed_sec`
  - 인덱싱 완료까지 전체 시간
- `smoke query latency`
  - `agent.run()` end-to-end 시간

### Cost

- `api_calls`
  - 실제 context 생성 호출 수
- `parent_context_calls`
  - parent section용 호출 수
- `child_context_calls`
  - child chunk용 호출 수
- `prompt_tokens`, `output_tokens`
  - contextual ingest usage metadata 합계
- `estimated_ingest_cost_usd`
  - config 단가 기준 추정치
  - sample config는 `gemini-2.5-flash` 표준 요금 기준으로 `input $0.30 / 1M tokens`, `output $2.50 / 1M tokens`를 사용한다.
  - benchmark의 `llm.batch()`는 Google Batch API가 아니라 병렬 표준 호출이므로 표준 요금을 기준으로 계산한다.

### Retrieval / Answer Quality

- `retrieval_hit_at_k`
  - 기대 회사/연도/섹션을 만족하는 문서가 top-k 안에 하나라도 있으면 `1.0`
- `section_match_rate`
  - retrieved docs 중 기대 section과 일치하는 비율
- `citation_coverage`
  - citation에 기대 `company`, `year`, `section`이 반영된 비율
- `contamination_rate`
  - retrieved docs 중 기대 회사/연도와 다른 문서가 섞인 비율
- `faithfulness`
  - answer가 retrieved context에 얼마나 근거하는지에 대한 judge score
- `answer_relevancy`
  - question / answer cosine similarity
- `context_recall`
  - canonical dataset의 evidence quote가 retrieved context에 얼마나 회수됐는지

## Section Alias Policy

숫자 질의는 단일 section만 정답으로 보지 않는다.  
현재 `numeric_fact` category는 아래 section을 동급 alias로 허용한다.

- `매출현황`
- `재무제표`
- `요약재무`
- `연결재무제표`
- `연결재무제표 주석`

이 alias는 screening의 `retrieval_hit_at_k`, `section_match_rate`, `citation_coverage` 계산에 반영한다.

## Screening 통과 기준

아래 중 하나라도 깨지면 탈락이다.

- risk smoke query 실패
- wrong-company contamination
- citation mismatch
- risk, business 또는 numeric query에서 `retrieval_hit_at_k == 0`
- missing-information query에서 근거 없는 단정 답변

정량 기준:

- baseline 대비 `retrieval_hit_at_k` 하락폭 > `0.10`이면 탈락
- baseline 대비 `section_match_rate` 하락폭 > `0.15`이면 탈락

## 실험 매트릭스 v1

문서:

- 삼성전자 2024 사업보고서
- SK하이닉스 2024 사업보고서
- NAVER 2024 사업보고서

후보:

- `contextual_all_2500_320`
- `contextual_parent_only_2500_320`
- `contextual_parent_hybrid_2500_320`
- `contextual_selective_v2_2500_320`

설정:

- `screening.parallel_experiments = 2`

승자 선정 우선순위:

1. cross-company screening pass count
2. critical category miss 여부
3. baseline 대비 API calls 감소율
4. baseline 대비 ingest 시간 감소율
5. full eval의 `faithfulness`, `context_recall`
6. reviewer artifact에서 확인되는 정성적 오류 유무

## 결과 산출물

- `benchmarks/results/<run_name>/results.json`
- `benchmarks/results/<run_name>/summary.csv`
- `benchmarks/results/<run_name>/summary.md`
- `benchmarks/results/<run_name>/review.csv`
- `benchmarks/results/<run_name>/review.md`
- `benchmarks/results/<run_name>/cross_company_summary.csv`
- `benchmarks/results/<run_name>/cross_company_summary.md`

결과에는 아래 해석용 정보가 포함된다.

- baseline 대비 API calls 감소율
- baseline 대비 ingest 시간 감소율
- baseline 대비 estimated cost 감소율
- screening pass 여부
- contamination rate
- miss가 난 질문의 `failure_examples`
- selector가 어떤 이유로 chunk를 contextualize했는지에 대한 `selector_reason_counts`
- 질문별 `answer_key`, evidence quote, 실제 answer, top retrieved를 나란히 볼 수 있는 review artifact
- 기업별 screening 결과와 후보별 cross-company aggregate
- partial / completed 상태를 나타내는 `run_status`, `completed_companies`, `pending_companies`

## 최신 기록

현재 repo에 포함할 대표 run:

- `benchmarks/results/v2_low_cost_2026-04-16`
- `benchmarks/results/v3_generalization_2026-04-16`
- `benchmarks/results/dev_fast_cache_check_2026-04-17`

`v3_generalization_2026-04-16`의 핵심 결과:

- 공통 승자 없음
- `삼성전자`: `contextual_parent_hybrid_2500_320`만 screening 통과
- `SK하이닉스`: `contextual_all_2500_320`만 screening 통과
- `NAVER`: 통과 후보 없음

현재 해석:

- 저비용 후보 비교 자체는 유효했지만, 기본값 후보를 고르기에는 아직 일반화가 부족하다
- 특히 `NAVER`는 비정상적인 `section_path`가 반복되어 parser / section extraction 점검이 선행되어야 한다
- 숫자 질의는 `연결재무제표`, `연결재무제표 주석`까지 허용할지 section alias 정책을 더 다듬을 필요가 있다
- answer-level judge score는 retrieval / actual answer와 어긋나는 케이스가 있어, 결과 해석 시 reviewer artifact를 함께 봐야 한다

`dev_fast_cache_check_2026-04-17`의 핵심 결과:

- `dev_fast` 프로파일로 삼성전자 1회사 screening-only를 2회 연속 실행
- 1차 run: 약 13분 16초
- 2차 run: 약 5분 27초
- 2차 run에서는 모든 후보가 `cache_hit = true`, `cache_level = store`
- 2차 run ingest는 `api_calls = 0`, `elapsed_sec = 0.0`

현재 해석:

- 같은 보고서 / 같은 청킹 / 같은 ingest mode 재실행에서는 contextual ingest API 비용을 다시 쓰지 않는다
- 반복 실험에서 남는 시간은 대부분 query / screening 평가 쪽이다
- 따라서 일상 루프는 `dev_fast`, release-grade 비교는 회사별 분리 실행이 적절하다

## 실행 방법

fast iteration 예시:

```bash
python -m src.ops.benchmark_runner --config benchmarks/profiles/dev_fast.json
```

release generalization을 회사별로 분리 실행하는 예시:

```bash
python -m src.ops.benchmark_runner --config benchmarks/profiles/release_generalization.json --company-run-id samsung_2024
python -m src.ops.benchmark_runner --config benchmarks/profiles/release_generalization.json --company-run-id skhynix_2024
python -m src.ops.benchmark_runner --config benchmarks/profiles/release_generalization.json --company-run-id naver_2024
```

위처럼 분리 실행하면 회사별 결과를 먼저 남기고, root `results.json` / `cross_company_summary.*`는 partial summary로 계속 갱신된다.
