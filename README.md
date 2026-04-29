# DART 공시 분석 RAG Agent

DART 전자공시 문서를 대상으로, **구조를 보존한 retrieval**과 **근거 통제가 가능한 answer generation**을 실험하는 한국어 RAG 시스템입니다.  
이 프로젝트의 중심은 “LLM에게 문서를 읽히는 것”보다, **비표준 공시 문서를 어떻게 구조화하고, 어떤 평가 기준 위에서 RAG/agent를 개선할 것인가**에 있습니다.

## 핵심 기술 결정

### 1. 구조 우선 ingestion

- DART XML 전용 parser로 `SECTION-*`, `TITLE`, `P`, `TABLE`, `TABLE-GROUP`를 직접 해석
- 일반 HTML splitter 대신 **문서 구조를 보존하는 청킹**을 채택
- parent-child metadata, section path, table context를 retrieval과 citation의 기본 단위로 사용

### 2. 한국어 공시용 retrieval stack

- multilingual embedding + BM25 + RRF hybrid retrieval
- `chunk_uid` 기반 dedup
- company / year / section metadata filtering
- child chunk로 검색하고 parent section으로 reasoning context를 구성하는 **parent-child retrieval**

### 3. answer generation을 free-form generation이 아니라 evidence compression으로 재설계

- `retrieve -> evidence -> compress -> validate -> cite`
- structured evidence를 먼저 만들고, 답변은 그 근거를 질문 범위에 맞게 압축하는 방식으로 이동 중
- 최근에는 `selected_claim_ids`, `kept_claim_ids`, `dropped_claim_ids`, `unsupported_sentences` 같은 typed artifact를 남겨, 답변 생성 경로를 추적 가능하게 만들었다

### 4. 평가를 먼저 고정하고 시스템을 바꾸는 방식

- multi-company benchmark 전에 **single-document Golden Dataset**을 먼저 만드는 방향으로 전환
- 숫자 질문은 generic `faithfulness`만으로 평가하지 않고 numeric evaluator를 별도 분리
- retrieval / generation / numeric / refusal metric을 분리해, 어떤 실패가 retrieval 문제인지 generation 문제인지 설명 가능하게 만드는 것이 현재의 핵심 방향이다

## 현재 기본 구조

```text
질문
  -> classify
  -> extract
  -> retrieve
  -> build_structured_evidence
  -> compress
  -> validate
  -> cite
  -> 답변
```

현재 검색은 child chunk 기준으로 수행하고, reasoning context는 parent section을 우선 사용합니다.

## 현재 기본값

- Embedding: `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2`
- Collection: `dart_reports_v2`
- Chunk size / overlap: `2500 / 320`
- Ingest mode baseline: `contextual_all`
- Retrieval: Dense + BM25 + RRF + rerank
- Reasoning: evidence-first

## 현재 실험 방향

이 프로젝트는 최근 실험을 통해 “더 싼 ingest mode를 찾는 것”보다 **평가 기준을 먼저 고정하는 것**이 더 중요하다는 결론에 도달했습니다.

현재 우선순위:

1. 삼성전자 2024 사업보고서 기준 single-document Golden Dataset 정리
2. metric spec 고정
3. single-document benchmark lab 안정화
4. 그 다음에만 retrieval / compression / validation을 다시 개선

즉 지금의 기준선은 다기업 benchmark보다도, **단일 문서에서 retrieval / generation / numeric / refusal을 어떻게 해석할지 먼저 고정하는 것**입니다.

## 프로젝트 구조

```text
src/
  ingestion/      DART 수집
  processing/     DART XML 파싱 및 청킹
  storage/        ChromaDB / BM25 / parent store
  agent/          LangGraph 기반 분석 로직
  api/            FastAPI 라우터
  ops/            evaluator / benchmark runner
benchmarks/
  experiment_matrix.sample.json
  eval_dataset.template.json
  results/
docs/
  README.md
  overview/
  architecture/
  evaluation/
  planning/
  history/
app.py            Streamlit UI
main.py           FastAPI entrypoint
```

## 실행

환경 준비:

```bash
uv venv .venv
.venv\Scripts\activate
uv pip install -r requirements.txt
```

`.env`:

```text
GOOGLE_API_KEY=...
DART_API_KEY=...
```

Streamlit:

```bash
streamlit run app.py
```

FastAPI:

```bash
uvicorn main:app --reload --port 8000
```

## Benchmark 실행

```bash
python -m src.ops.benchmark_runner --config benchmarks/experiment_matrix.sample.json
```

빠른 반복 실험:

```bash
python -m src.ops.benchmark_runner --config benchmarks/profiles/dev_fast.json
```

일반화 검증:

```bash
python -m src.ops.benchmark_runner --config benchmarks/profiles/release_generalization.json --company-run-id samsung_2024
python -m src.ops.benchmark_runner --config benchmarks/profiles/release_generalization.json --company-run-id skhynix_2024
python -m src.ops.benchmark_runner --config benchmarks/profiles/release_generalization.json --company-run-id naver_2024
```

결과물:

- `benchmarks/results/.../results.json`
- `benchmarks/results/.../summary.csv`
- `benchmarks/results/.../summary.md`

자세한 설명은 [docs/evaluation/benchmarking.md](docs/evaluation/benchmarking.md)를 참고하세요.

## 참고 문서

- [docs/overview/technical_highlights.md](docs/overview/technical_highlights.md): 프로젝트 핵심 기술 포인트 요약
- [DECISIONS.md](DECISIONS.md): 중요한 설계 판단과 근거
- [docs/evaluation/benchmarking.md](docs/evaluation/benchmarking.md): benchmark 구조와 metric 해석
- [docs/evaluation/single_document_eval_strategy.md](docs/evaluation/single_document_eval_strategy.md): 단일 문서 기준선 전략
- [docs/evaluation/evaluation_metrics_v1.md](docs/evaluation/evaluation_metrics_v1.md): metric spec v1
- [docs/history/experiment_history.md](docs/history/experiment_history.md): 버전별 코드/실험 변화와 해석
- [CONTEXT.md](CONTEXT.md): 현재 상태와 handoff 메모
- [PLAN.md](PLAN.md): 다음 실험 계획
