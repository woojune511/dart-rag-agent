# DART 기반 기업 공시 분석 AI Agent — 프로젝트 플랜

## 프로젝트 목적

**DART(전자공시시스템) 공개 데이터를 기반으로, 자연어 질문에 답하는 기업 공시 분석 AI Agent 구축**

### 지향하는 JD 역량
- RAG 아키텍처 설계 및 구현 (Vector DB + Hybrid Search)
- LangGraph 기반 AI Agent 오케스트레이션
- 비즈니스 요구사항 → 기술 스펙 전환 역량
- MLOps: 평가 파이프라인 + 실험 추적
- FastAPI 기반 서비스 가능한 백엔드

### 지원 쿼리 예시
- "삼성전자 2023년 주요 리스크 요인은 무엇인가요?"
- "카카오와 네이버의 2023년 영업이익을 비교해주세요"
- "네이버 최근 3년간 매출 성장 트렌드를 분석해주세요"
- "삼성전자 반도체 부문의 사업 현황을 요약해주세요"

---

## 현재 코드베이스 상태

### 디렉토리 구조
```
research agent/
├── src/
│   ├── ingestion/
│   │   └── arxiv_fetcher.py      # ArXiv API + DuckDuckGo 검색 (완성)
│   ├── processing/
│   │   ├── pdf_parser.py         # pymupdf4llm 기반 파싱 + 청킹 (완성)
│   │   ├── ast_parser.py         # Python 코드 AST 추출 (완성)
│   │   └── github_downloader.py  # GitHub repo ZIP 다운로드 (완성)
│   ├── storage/
│   │   └── vector_store.py       # ChromaDB + BM25 + RRF Hybrid Search (완성)
│   ├── agent/
│   │   ├── rag_chain.py          # Gemini 기반 RAG 체인 (완성)
│   │   ├── filter_agent.py       # 논문 필터링 (인용수 + LLM 평가) (완성)
│   │   └── graph.py              # LangGraph 멀티에이전트 오케스트레이터 (완성)
│   ├── api/                      # FastAPI 엔드포인트 (미구현)
│   └── ops/                      # MLflow 평가 파이프라인 (미구현)
├── data/
│   ├── papers/                   # 다운로드된 PDF
│   ├── repos/                    # 클론된 GitHub 레포
│   └── chroma_db/                # ChromaDB 영속 저장소
├── mlruns/                       # MLflow 로컬 트래킹
├── app.py                        # Streamlit UI (3탭: Ingestion / RAG QA / LangGraph)
├── main.py                       # CLI 진입점
└── requirements.txt
```

### 구현 완료 항목
| 모듈 | 상태 | 설명 |
|---|---|---|
| PDF 파싱 | 완성 | pymupdf4llm → Markdown → 헤더 기반 청킹 |
| Hybrid Search | 완성 | ChromaDB(Dense) + BM25(Sparse) + RRF 융합 |
| RAG 체인 | 완성 | 검색 → Gemini 합성 → 출처 인용 |
| LangGraph Agent | 완성 | 4개 인텐트 분류 + 멀티스텝 실행 |
| Streamlit UI | 완성 | Ingestion / QA / 오케스트레이션 탭 |
| ArXiv Ingestion | 완성 | API 검색 + 인용 필터링 + 자동 다운로드 |
| GitHub 분석 | 완성 | AST 추출 + 코드 청킹 + RAG QA |
| MLflow 트래킹 | 부분 | 기본 로깅만 구현됨 |
| FastAPI | 미구현 | `src/api/` 디렉토리만 존재 |
| 평가 파이프라인 | 미구현 | `src/ops/` 디렉토리만 존재 |

---

## 현재 문제점 및 개선 필요 사항

### 1. 도메인 특화 부재
- 현재 시스템은 arXiv 논문에 최적화되어 있어 재무 문서의 특성을 처리하지 못함
- 재무제표 테이블, 수치 데이터가 많은 문서 구조에 대한 파싱 로직 없음
- 청크 메타데이터에 재무 도메인 필드 (회사명, 연도, 보고서 종류, 섹션 분류) 부재

### 2. 데이터 수집 레이어 교체 필요
- `arxiv_fetcher.py`를 DART API fetcher로 대체해야 함
- DART API 키 발급 및 연동 필요
- 공시 문서 종류별 처리 로직 필요 (사업보고서, 분기보고서, 반기보고서)

### 3. Agent 로직 재설계 필요
- 현재 `graph.py`는 논문 리서치 시나리오에 맞춰진 인텐트 분류
- 재무 분석 시나리오에 맞게 노드 재설계 필요:
  - 기업명/연도 엔티티 추출
  - 단일 기업 QA vs. 기업 간 비교 vs. 시계열 트렌드 분류
- 멀티 문서 추론(여러 기업, 여러 연도 동시 검색) 미지원

### 4. 평가 파이프라인 없음
- RAG 품질을 정량적으로 측정할 방법 없음
- 프롬프트/청크 크기/검색 전략 변경 시 성능 비교 불가
- `src/ops/`가 비어있어 MLOps 역량 어필 불가

### 5. API 서비스화 미완
- `src/api/`가 비어있어 외부에서 접근 가능한 인터페이스 없음
- 포트폴리오에서 "서비스 가능한 형태"를 보여주기 어려움

### 6. LangGraph 메모리 없음
- 현재 멀티턴 대화 시 이전 컨텍스트 유지 안 됨
- SQL Checkpointer 미구현

---

## 구현 계획

### Phase 1 — DART 데이터 수집 레이어
**목표**: DART API 연동 및 공시 문서 자동 수집

**신규 파일**: `src/ingestion/dart_fetcher.py`

```python
# 주요 기능
- get_company_code(company_name)     # 기업명 → DART 고유 코드 조회
- get_report_list(corp_code, year)   # 공시 목록 조회
- download_report_pdf(rcept_no)      # 보고서 PDF 다운로드
```

**수집 대상 기업 (초기)**:
- 삼성전자, SK하이닉스, 네이버, 카카오, LG에너지솔루션
- 2021 ~ 2023년 사업보고서 (연 1회) → 총 15개 문서

**환경 변수 추가**: `DART_API_KEY`

---

### Phase 2 — 재무 문서 파싱 특화
**목표**: 재무 문서 구조에 맞는 파싱 및 메타데이터 부착

**신규 파일**: `src/processing/financial_parser.py`

```python
# 기존 pdf_parser.py 확장
- 재무제표 테이블 구조 보존 처리
- 섹션 자동 분류:
    "사업의 개요" | "주요 리스크" | "재무 현황" | "임원 현황" | "기타"
- 청크 메타데이터 스키마:
    {
      "company": "삼성전자",
      "ticker": "005930",
      "year": 2023,
      "report_type": "사업보고서",
      "section": "주요 리스크",
      "source_page": 42
    }
```

---

### Phase 3 — Financial Analysis Agent (핵심)
**목표**: 재무 분석 시나리오에 최적화된 LangGraph Agent 재설계

**신규 파일**: `src/agent/financial_graph.py`

**Agent 그래프 설계**:
```
사용자 질문
    ↓
[query_classifier_node]
    단순 QA / 기업 간 비교 / 시계열 트렌드 / 리스크 분석
    ↓
[entity_extractor_node]
    기업명 → DART 코드, 연도 범위 추출
    ↓
[retrieval_node]
    Hybrid Search (기업/연도 메타데이터 필터 적용)
    ↓
[analyst_node]
    재무 수치 + 텍스트 컨텍스트 → 구조화된 분석 생성
    ↓
[citation_node]
    출처 명시 (기업명, 보고서명, 제출 연도, 섹션)
    ↓
최종 답변
```

**쿼리 유형별 처리**:
| 유형 | 설명 | 특이사항 |
|---|---|---|
| 단순 QA | 특정 기업의 단일 질문 | 단일 문서 검색 |
| 기업 간 비교 | 2개 이상 기업 비교 | 병렬 검색 후 합성 |
| 시계열 트렌드 | 연도별 변화 분석 | 동일 기업 복수 연도 검색 |
| 리스크 분석 | 리스크 섹션 집중 검색 | 섹션 필터 적용 |

---

### Phase 4 — 평가 파이프라인 (Ops)
**목표**: RAG 품질 정량 측정 및 MLflow 실험 추적

**신규 파일**: `src/ops/evaluator.py`

**평가 데이터셋**: 질문 20개 + 수동 작성 정답
```
Q: "삼성전자 2023년 사업보고서에서 언급된 주요 리스크 3가지는?"
A: [정답 텍스트]
```

**평가 지표**:
| 지표 | 설명 | 측정 방법 |
|---|---|---|
| Faithfulness | 답변이 문서 근거에 충실한가 | LLM-as-judge |
| Answer Relevancy | 질문과 답변의 관련성 | Embedding 유사도 |
| Context Recall | 필요한 청크를 잘 검색했는가 | 정답 커버리지 |

**MLflow 실험 추적**:
- 변수: 프롬프트 버전 / 청크 크기(256, 512, 1024) / 검색 전략(dense, bm25, hybrid)
- 자동 로깅: 지표 + 파라미터 + 아티팩트

---

### Phase 5 — API 서비스화 + UI 완성
**목표**: FastAPI 엔드포인트 구현 + Streamlit UI 확장

**신규 파일**: `src/api/financial_router.py`

```
POST /ingest
    body: { "company": "삼성전자", "years": [2021, 2022, 2023] }
    → DART에서 자동 수집 + 파싱 + 벡터 DB 적재

POST /query
    body: { "question": "삼성전자 2023년 주요 리스크는?" }
    → Financial Agent 실행 → 분석 결과 반환

GET /companies
    → 현재 적재된 기업 목록 조회
```

**Streamlit UI 탭 재구성**:
- Tab 1: 기업 데이터 수집 (기업 선택 + 연도 선택 + 수집 실행)
- Tab 2: 질문 분석 (자연어 입력 → Agent 실행 → 답변 + 출처)
- Tab 3: 평가 대시보드 (지표 시각화 + MLflow 연동)

---

## 전체 타임라인

| Phase | 내용 | 예상 소요 |
|---|---|---|
| Phase 1 | DART API 연동 + 문서 수집 | 2~3일 |
| Phase 2 | 재무 문서 파싱 특화 | 2~3일 |
| Phase 3 | Financial Agent 설계 및 구현 | 5~7일 |
| Phase 4 | 평가 파이프라인 구축 | 2~3일 |
| Phase 5 | API + UI 마무리 | 2~3일 |

---

## 기술 스택 (변경/추가 사항)

| 분류 | 기존 | 변경/추가 |
|---|---|---|
| 데이터 수집 | arxiv, duckduckgo-search | **dart-fss** (DART API Python 래퍼) |
| LLM | Gemini 2.5-flash | 유지 |
| Vector DB | ChromaDB | 유지 |
| Orchestration | LangGraph | 유지 (그래프 재설계) |
| 평가 | 없음 | **RAGAS** 또는 커스텀 LLM judge |
| API | 미구현 | **FastAPI** |
| 환경 변수 | GOOGLE_API_KEY | + **DART_API_KEY** |

---

## 포트폴리오 어필 포인트

1. **RAG 설계 역량**: Hybrid Search + 재무 도메인 특화 청킹 전략
2. **Agent 오케스트레이션**: LangGraph 멀티스텝 분석 플로우 (분류 → 검색 → 합성 → 인용)
3. **Ops/MLOps**: 평가 데이터셋 구축 + MLflow 실험 관리
4. **서비스 가능한 백엔드**: FastAPI REST API
5. **비즈니스 임팩트 설명 가능**: 공개 데이터 기반, 실제 재현 가능한 데모
