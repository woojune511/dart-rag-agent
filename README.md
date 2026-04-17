# DART 공시 분석 RAG Agent

DART 전자공시 문서를 수집하고, 기업 공시에 대해 근거 기반 답변을 생성하는 한국어 RAG 분석 프로젝트입니다.  
현재 시스템은 DART 수집, XML 구조 파싱, 구조 기반 청킹, hybrid retrieval, parent-child/contextual retrieval, evidence-first reasoning, FastAPI/Streamlit 인터페이스, MLflow 기반 평가까지 포함합니다.

## 핵심 특징

- DART XML 구조를 직접 해석하는 전용 parser
- ChromaDB + BM25 + RRF 기반 hybrid retrieval
- parent-child retrieval과 contextual retrieval 결합
- evidence-first answer synthesis
- single-company contamination 방지를 위한 strict metadata filtering
- benchmark runner 기반 정확도/속도/API 비용 비교 실험

## 현재 기본 구조

```text
질문
  -> classify
  -> extract
  -> retrieve
  -> evidence
  -> analyze
  -> cite
  -> 답변
```

검색은 자식 청크 기준으로 수행하고, 답변 컨텍스트는 부모 섹션 텍스트를 우선 사용합니다.

## 현재 기본값

- Embedding: `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2`
- Collection: `dart_reports_v2`
- Chunk size / overlap: `2500 / 320`
- Ingest mode baseline: `contextual_all`
- Retrieval: Dense + BM25 + RRF + rerank
- Reasoning: evidence-first

## 현재 benchmark 상태

현재 benchmark는 두 층으로 운영합니다.

- `dev_fast`
  - 삼성전자 1회사, screening only
  - 빠른 반복 실험용
- `release_generalization`
  - 삼성전자 / SK하이닉스 / NAVER
  - shortlist 후보의 일반화 검증용

최신 일반화 실험은 [v4_generalization_fix_2026-04-17](/C:/Users/admin/Desktop/dart-rag-agent/benchmarks/results/v4_generalization_fix_2026-04-17/cross_company_summary.md) 입니다.

현재 상태 요약:

- 3개 기업 기준 공통 screening 통과 후보는 아직 없습니다.
- `contextual_parent_only_2500_320`
  - 평균 API 호출과 ingest 시간은 크게 줄였지만
  - numeric / risk / R&D 질문에서 abstention이 반복됩니다.
- `contextual_selective_v2_2500_320`
  - 비용 절감 폭은 크지만
  - business overview / risk retrieval miss가 남아 있습니다.
- `contextual_parent_hybrid_2500_320`
  - 품질 보완 효과는 일부 있으나
  - 평균 비용이 baseline보다 비싸 실익이 약합니다.
- `contextual_all_2500_320`
  - 여전히 가장 안정적인 baseline이지만
  - NAVER business overview와 missing-information에서 실패가 남아 있습니다.

즉 현재는 기본값을 더 싼 후보로 바꾸기보다, `contextual_all_2500_320`을 기준선으로 유지하면서 query-stage 실패와 기업별 retrieval 약점을 줄이는 단계입니다.

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
  benchmarking.md
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

자세한 설명은 [docs/benchmarking.md](docs/benchmarking.md)를 참고하세요.

## 참고 문서

- [CONTEXT.md](CONTEXT.md): 현재 상태와 handoff 메모
- [DECISIONS.md](DECISIONS.md): 핵심 기술 결정 로그
- [PLAN.md](PLAN.md): 다음 실험 계획
- [docs/experiment_history.md](docs/experiment_history.md): 버전별 코드/실험 변화와 결과 요약
- [REVIEW_FINDINGS.md](REVIEW_FINDINGS.md): 코드 리뷰 아카이브
