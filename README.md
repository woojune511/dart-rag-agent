# DART 기업 공시 분석 AI Agent

DART(전자공시시스템) 공개 데이터를 기반으로 자연어 질문에 답하는 기업 공시 분석 AI Agent.
사업보고서·분기보고서를 자동 수집하고, Hybrid Search + LangGraph 기반 멀티스텝 분석을 수행한다.

## 지원 쿼리 예시

- "삼성전자 2023년 주요 리스크 요인은 무엇인가요?"
- "카카오와 네이버의 2023년 영업이익을 비교해주세요"
- "네이버 최근 3년간 매출 성장 트렌드를 분석해주세요"

## 기술 스택

| 분류 | 기술 |
|---|---|
| LLM / Orchestration | LangGraph, LangChain, Google Gemini 2.5-flash |
| Search / RAG | ChromaDB, BM25, RRF (Reciprocal Rank Fusion) |
| Data | DART OpenAPI, pymupdf4llm |
| MLOps | MLflow |
| API | FastAPI |
| 환경 | Python, uv |

## 프로젝트 구조

```
src/
├── ingestion/
│   └── dart_fetcher.py       DART API 연동 및 공시 문서 수집
├── processing/
│   ├── pdf_parser.py         PDF → Markdown 파싱 및 헤더 기반 청킹
│   └── financial_parser.py   재무 문서 특화 파싱 (섹션 분류, 메타데이터)
├── storage/
│   └── vector_store.py       ChromaDB + BM25 Hybrid Search
├── agent/
│   ├── rag_chain.py          RAG 체인 (검색 → LLM 합성 → 출처 인용)
│   └── financial_graph.py    LangGraph Financial Analysis Agent
├── api/
│   └── financial_router.py   FastAPI 엔드포인트
└── ops/
    └── evaluator.py          RAG 평가 파이프라인 (MLflow 연동)
```

## 구현 현황

- [x] Phase 1 — DART API 연동 및 공시 문서 수집
- [ ] Phase 2 — 재무 문서 파싱 특화
- [ ] Phase 3 — Financial Analysis Agent (LangGraph)
- [ ] Phase 4 — 평가 파이프라인 (MLflow)
- [ ] Phase 5 — FastAPI + Streamlit UI

## 로컬 실행

```bash
# 가상환경 설치
uv venv
.venv\Scripts\activate
uv pip install -r requirements.txt
```

`.env` 파일에 API 키를 설정한다:

```
GOOGLE_API_KEY=...   # https://aistudio.google.com
DART_API_KEY=...     # https://opendart.fss.or.kr/intro/main.do
```

```bash
# 데이터 수집 스모크 테스트 (DART_API_KEY 발급 후)
cd src && python -m ingestion.dart_fetcher
```

## 상세 계획

구현 계획 및 기술 결정 사항은 [PLAN.md](PLAN.md) 참고.
