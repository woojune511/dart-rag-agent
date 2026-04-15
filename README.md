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

## 최근 benchmark 결과

기준 문서:

- 삼성전자 2024 사업보고서
- 접수번호 `20250311001085`

1차 screening / 2차 full eval 결과:

| Experiment | Ingest (s) | Chunks | API Calls | Screen Hit@k | Screen Section | Full Faithfulness | Full Relevancy | Full Recall |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| `plain_2500_320` | 19.183 | 300 | 0 | 0.800 | 0.125 | - | - | - |
| `contextual_all_2500_320` | 558.723 | 300 | 300 | 1.000 | 0.250 | 0.400 | 0.651 | 0.500 |
| `contextual_parent_only_2500_320` | 67.964 | 300 | 40 | 0.800 | 0.175 | - | - | - |
| `contextual_selective_2500_320` | 331.002 | 300 | 289 | 0.800 | 0.150 | - | - | - |
| `contextual_1500_200` | 774.632 | 502 | 502 | 0.800 | 0.225 | 0.640 | 0.500 | 0.300 |

현재 screening 기준을 통과한 후보는 `contextual_all_2500_320` 하나입니다.

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

결과물:

- `benchmarks/results/.../results.json`
- `benchmarks/results/.../summary.csv`
- `benchmarks/results/.../summary.md`

자세한 설명은 [docs/benchmarking.md](docs/benchmarking.md)를 참고하세요.

## 참고 문서

- [CONTEXT.md](CONTEXT.md): 현재 상태와 handoff 메모
- [DECISIONS.md](DECISIONS.md): 핵심 기술 결정 로그
- [PLAN.md](PLAN.md): 다음 실험 계획
- [REVIEW_FINDINGS.md](REVIEW_FINDINGS.md): 코드 리뷰 아카이브
