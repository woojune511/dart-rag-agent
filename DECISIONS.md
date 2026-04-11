# 기술적 결정 & 문제 해결 로그

> 각 Phase에서 발생한 문제, 근본 원인 분석, 시도한 해결책, 채택한 해결책, 결과를 기록.
> 실패한 시도도 포함하여 의사결정 맥락을 보존.

---

## Phase 1 — DART 데이터 수집 레이어

### 결정 1: DART 문서 포맷 — ZIP 압축 해제 후 HTML 저장

**문제**: DART Open API의 `document.zip` 엔드포인트가 실제 문서를 무슨 포맷으로 반환하는지 불명확했음.

**분석**:
- DART API 문서에는 "PDF 또는 HTML" 형식이라고만 명시
- 실제 다운로드해보니 ZIP 내부에 `.html` 확장자 파일이 존재
- 그러나 해당 파일은 표준 HTML이 아닌 **DART 독자 XML 포맷** (SECTION-1, SECTION-2, TABLE-GROUP 등 비표준 태그)

**채택한 해결책**: `.html` 확장자 그대로 저장, 파싱은 lxml XML 파서 사용 (Phase 2에서 처리)

**결과**: `data/reports/삼성전자/2023_사업보고서_{rcept_no}.html` 형태로 저장 성공 (4.4MB)

---

### 결정 2: 기업 코드 조회 — 부분 일치 폴백

**문제**: DART API의 기업 코드 조회는 정확한 법인명을 요구하지만, 사용자는 "삼성전자"처럼 줄인 이름을 입력함.

**분석**:
- `get_corp_code("삼성전자")` 호출 시 "삼성전자주식회사"와 매칭되지 않는 경우 발생
- DART의 corp_code 전체 목록이 ZIP으로 제공됨 (`corpCode.xml`)

**채택한 해결책**:
1. 전체 법인 목록 `corpCode.xml`을 캐싱
2. 정확 일치 → 없으면 부분 일치 폴백 (`company_name in corp_name`)
3. 복수 매칭 시 첫 번째 결과 반환

**결과**: "삼성전자" → "삼성전자주식회사" 정상 매칭

---

## Phase 2 — DART XML 파서

### 결정 3: lxml XMLParser(recover=True) 사용

**문제**: DART XML 파일이 표준 XML 명세를 위반하는 경우 존재 (미닫힌 태그, 인코딩 오류).

**분석**:
- Python 기본 `xml.etree.ElementTree`로 파싱 시 `ParseError` 발생
- DART 문서는 비표준 태그(SECTION-1, TABLE-GROUP 등)와 HTML 엔티티가 혼재

**채택한 해결책**: `lxml.etree.XMLParser(recover=True, encoding="utf-8", huge_tree=True)`
- `recover=True`: 비표준 구조 복구
- `huge_tree=True`: 4MB 이상 대용량 파일 파싱 허용

**결과**: 4.4MB 삼성전자 사업보고서 정상 파싱

---

### 결정 4: SECTION-N 태그를 섹션 경계로 사용

**문제**: DART XML 구조에서 섹션을 어떻게 분리할 것인가.

**분석**:
- DART XML 계층: `BODY > SECTION-1 > [SECTION-2 > SECTION-3]`
- 각 SECTION-N에는 `<TITLE ATOC="Y">` 헤더 태그가 존재
- 목차 항목(ATOC="Y")이 섹션 제목으로 사용됨

**채택한 해결책**:
- `root.iter()`로 모든 SECTION-1/2/3 탐색
- 각 SECTION-N의 직속 자식 중 `TITLE ATOC="Y"` 찾아 섹션 제목으로 사용
- SECTION-N 내 하위 SECTION-N은 별도 섹션으로 처리 (재귀 제외)

**결과**: 삼성전자 2023 사업보고서 → 40개 섹션 추출

---

### 문제 5 (버그): `id()` 기반 하위 섹션 건너뛰기 실패

**현상**: 초기 구현에서 `_extract_sections` 함수가 0개 섹션을 반환.

**근본 원인**:
```python
# 잘못된 코드
skip_descendants: set = set()
for section in root.iter():
    if id(section) in skip_descendants:  # 항상 False!
        continue
    ...
    for desc in section.iter():
        skip_descendants.add(id(desc))  # lxml이 프록시 ID를 재사용함
```
lxml은 XML 원소를 Python 객체로 접근할 때마다 새 프록시를 생성하고 `id()`가 달라짐. 즉 추가한 ID가 다음 iteration에서 매칭되지 않음.

**실패한 해결책**: `id()` 대신 `element.getroottree().getpath(element)` 시도 — 성능 저하 심각.

**채택한 해결책**: `id()` 방식 전면 폐기. 대신 `_collect_blocks` 재귀 함수에서 SECTION-N 태그를 만나면 즉시 `return` 처리:
```python
def process(elem):
    if elem.tag in _SECTION_TAGS:
        return   # 하위 섹션은 별도로 처리되므로 건너뜀
    ...
    for child in elem:
        process(child)
```

**결과**: 섹션 0개 → 40개 정상 추출

---

### 문제 6: LIBRARY 태그로 인한 "II. 사업의 내용" 콘텐츠 누락

**현상**: 리팩토링 후 "II. 사업의 내용" SECTION-1 직속 블록이 0개. 원래는 34,509자 존재.

**근본 원인**:
DART XML에서 SECTION-1의 자식 SECTION-2들이 `<LIBRARY>` 태그로 감싸여 있음:
```xml
<SECTION-1>
  <TITLE ATOC="Y">II. 사업의 내용</TITLE>
  <LIBRARY>           ← 이 태그 안에 SECTION-2들이 있음
    <SECTION-2>...</SECTION-2>
    <SECTION-2>...</SECTION-2>
  </LIBRARY>
</SECTION-1>
```
구 코드는 `child.iter()`로 LIBRARY를 투과하여 SECTION-2 내용까지 가져왔음 (의도치 않은 동작).
신 코드는 `process()` 재귀에서 LIBRARY를 만나면 자식을 순회하여 SECTION-N만 건너뜀 → 사실상 SECTION-2 콘텐츠가 올바르게 분리됨.

**결론**: 이것은 버그가 아니라 올바른 수정. "II. 사업의 내용"의 실제 콘텐츠는 하위 SECTION-2/3에 있으며, 각각 독립 섹션으로 처리됨.

---

### 결정 7: 섹션 분류 — 22개 키워드 매핑 테이블

**문제**: DART 섹션 제목은 보고서마다 표현이 다양함 ("5. 위험관리 및 파생거래", "리스크 관리" 등).

**분석**:
- 기업별/연도별로 섹션 명칭 변동 존재
- ML 분류기는 데이터 부족으로 불가
- 규칙 기반 키워드 매칭이 현실적

**채택한 해결책**: 22개 레이블 × 키워드 목록 (`_SECTION_LABELS`), 순서 우선 매칭 (더 구체적인 키워드가 앞)

**결과**: 삼성전자 2023 → 40개 섹션, 대부분 정확히 분류됨.
한계: "기타 참고사항" 같은 대형 복합 섹션은 단일 레이블으로 묶임.

---

### 결정 8: 콘텐츠 기반 동적 재분류

**문제**: "기타 참고사항" 섹션(16개 청크) 안에 리스크, 연구개발, 매출현황 등 다양한 주제가 혼재.

**분석**:
- 섹션 제목만으로는 세분화 불가
- 청크 텍스트에 키워드 스캔하면 올바른 레이블 부여 가능
- 모든 섹션에 적용하면 오분류 위험 (예: 재무제표 안의 "리스크" 언급 → 오분류)

**채택한 해결책**: "기타사업", "기타" 레이블에만 `_reclassify_by_content()` 적용
```python
if label not in ("기타사업", "기타"):
    return label   # 명확한 섹션은 그대로 유지
```

**결과**: 기존 "기타사업" 16청크 중 11개가 구체적 레이블(사업개요, 연구개발, 리스크, 매출현황)로 재분류

---

### 결정 9: 테이블 파이프 포맷 변환

**문제**: 재무제표 테이블을 어떻게 텍스트화할 것인가. 단순 텍스트 이어붙이기 시 계정명과 수치가 분리됨.

**분석**:
```
# 나쁜 예 (셀을 그냥 이어붙임)
"매출액 제54기 제53기 300조원 256조원"
# → 임베딩에서 "매출액"과 "300조원"의 연관성 약함

# 좋은 예 (행 단위 파이프 구분)
"매출액 | 제54기 | 제53기
300조원 | 256조원"
```
파이프 포맷이 행 내 계정명-수치 관계를 보존하여 BM25·임베딩 검색 품질 향상.

**채택한 해결책**:
```python
def _format_table(self, table_elem) -> str:
    rows = []
    for tr in table_elem.findall(".//TR"):
        cells = [_normalize("".join(cell.itertext())) for cell in tr if cell.tag in ("TD","TH","TU")]
        rows.append(" | ".join(c for c in cells if c))
    return "\n".join(rows)
```

---

## Phase 2 — 청킹 전략 개선 (주요 리팩토링)

### 문제 10: 순수 RecursiveCharacterTextSplitter의 구조 무시

**현상**: 초기 구현에서 전체 섹션 텍스트를 하나로 합친 후 `RecursiveCharacterTextSplitter`로 분할.

**근본 문제**:
1. **단락 경계 무시**: 1500자 한도에서 문장 중간에 잘림 (한국어 `"다."` 경계 우선 적용해도 불완전)
2. **표가 분할됨**: 재무제표 한 표가 두 청크에 걸쳐 저장 → "매출액"과 해당 금액이 다른 청크에 존재
3. **매우 작은 표가 단독 청크**: 1~2행짜리 참조 표도 단독 청크 → 과도한 청크 수 (615개 → 1,668개)

**사용자 지적**: "document structure-based chunking을 일단 하고 그 안에서 recursive character level chunking을 써야 할 것 같음"

---

### 해결 시도 1 (채택): 2단계 구조 기반 청킹 — Level 1 ALL-TABLE-STANDALONE

**설계**:
- Level 1: P 태그(단락) 블록을 chunk_size까지 누적, TABLE 블록은 항상 단독 청크
- Level 2: 누적 단락이 chunk_size 초과 시 RecursiveCharacterTextSplitter 폴백

**구현**: `_collect_blocks()` (P/TABLE 분리 수집) + `_chunk_blocks()` (누적 로직)

**결과 (문제)**:
```
청크 수: 1,668개 (615개 대비 2.7배 증가)
평균: 377자 / 중앙값: 98자
is_table 청크: 1,244개 (74.6%)
```
→ 소형 테이블(1~3행, 50~200자)이 모두 단독 청크가 되어 오히려 악화.

---

### 해결 시도 2 (채택): 2단계 구조 기반 청킹 — 대형 테이블만 단독

**근본 원인 재분석**: 모든 TABLE을 단독 처리하는 것이 문제. 재무 공시에는 소형 참조 표가 매우 많음.

**핵심 기준**: `standalone_threshold = chunk_size // 2 = 750자`
- 750자 이상 테이블 → 단독 청크 (재무제표 본표)
- 750자 미만 테이블 → 인접 단락과 함께 누적 (소형 참조 표)

```python
if is_table and len(text) >= standalone_threshold:
    flush_pending()          # 대형 테이블: 단독 청크
    result.append((text, True))
else:
    pending_texts.append(text)   # 소형 테이블 + 단락: 함께 누적
    pending_flags.append(is_table)
```

누적 블록의 is_table 판정: 테이블 문자 비중 > 50% 이면 True.

**결과 (개선)**:
```
청크 수: 573개  ← 합리적 (원래 615, 중간 1,668)
평균: 1,102자 / 중앙값: 1,345자  ← chunk_size=1500에 근접
최소: 9자 / 최대: 2,306자
is_table 청크: 451개 (78.7%)
1,000자 이상: 69.5%
50자 미만: 30개 (5.2%, XML 서브헤더 P 태그들, 불가피)
```

**대형 테이블 행 분할**: `_split_table_by_rows()` — 헤더 행(첫 행)을 각 서브청크에 반복 포함하여 계정명 컨텍스트 유지

---

### 결정 11: chunk_size=1500, chunk_overlap=200 파라미터

**근거**:
- DART 재무 공시의 단락(P 태그) 평균 200~400자
- 1,500자면 3~7개 단락 포함 → 충분한 컨텍스트
- overlap=200자: 단락 경계를 문자 수준에서 일부 공유 (구조 분할이 주이므로 overlap 역할 제한적)

---

## Phase 3 — LangGraph Financial Analysis Agent

### 결정 12: 5-노드 선형 파이프라인

**설계 근거**:
```
classify → extract → retrieve → analyze → cite → END
```
- 분기 없는 선형 구조: 구현 단순, 디버깅 용이
- 각 노드 단일 책임 원칙 유지
- 향후 `comparison` 타입에서 병렬 retrieve 분기 추가 가능한 구조 예비

**대안**: classify 결과에 따른 조건부 분기
- 거부 이유: 현재 쿼리 유형별 차이는 `_analyze`의 프롬프트 변경으로 충분히 처리 가능

---

### 결정 13: Gemini Structured Output으로 엔티티 추출

**문제**: 쿼리에서 기업명·연도·섹션 필터를 정확히 추출해야 메타데이터 필터링이 가능.

**채택한 해결책**: `llm.with_structured_output(EntityExtraction)` (Gemini function calling 기반)
```python
class EntityExtraction(BaseModel):
    companies: List[str]
    years: List[int]
    topic: str
    section_filter: Optional[str]  # 15개 섹션 레이블 중 하나 or null
```
Pydantic 스키마가 Gemini에게 자동으로 JSON Schema로 전달 → 타입 안전한 구조화 출력

---

### 결정 14: 메타데이터 후처리 필터링 (검색 후 필터)

**문제**: ChromaDB의 `where` 필터는 AND 조건만 지원, 복합 필터(기업 OR 조건 등) 불가.

**채택한 해결책**: k\*3개 먼저 검색 후 Python으로 후처리 필터링
```python
docs = vsm.search(enriched, k=self.k * 3)  # 오버샘플링
# 필터 후 결과가 2개 이상일 때만 적용 (너무 적으면 필터 해제)
if len(filtered) >= 2:
    docs = filtered
```
필터 순서: section_filter → company → year (구체적 → 일반 순)

---

### 결정 15: 쿼리 유형별 전용 프롬프트

| 유형 | 프롬프트 핵심 지시 |
|---|---|
| qa | 수치는 단위·출처 연도 함께 명시 |
| comparison | 항목별 표 형식 비교 |
| trend | 연도별 정리 + 원인·의미 해석 |
| risk | 항목별 나열 + 배경·잠재 영향 |

---

---

## Phase 4 — 평가 파이프라인

### 결정 16: 3가지 지표 선정 및 구현 방식

**배경**: RAG 품질 지표로는 RAGAS 라이브러리 사용이 일반적이나, 의존성 추가 없이 핵심 3지표만 직접 구현.

| 지표 | 측정 대상 | 구현 방식 | 선택 이유 |
|---|---|---|---|
| Faithfulness | 답변이 컨텍스트에만 근거하는가 | LLM-as-judge (Gemini) | hallucination 감지의 핵심 지표 |
| Answer Relevancy | 질문-답변 의미 유사도 | HuggingFace 임베딩 코사인 유사도 | 답변이 질문에서 벗어나는 경우 탐지 |
| Context Recall | 정답의 핵심 키워드가 검색 컨텍스트에 포함되는가 | 한국어 토큰 recall (2글자 이상) | 검색 단계 품질 측정 |

---

### 문제 17 (버그): `retrieved_docs`가 `agent.run()` 반환값에 없음

**현상**: 스모크 테스트 실행 시 `contexts=[]`로 faithfulness/recall 모두 계산 불가. 
첫 실행 결과 F=0.000, C=0.000.

**근본 원인**:
`FinancialAgent.run()`이 반환하는 dict에 `retrieved_docs` 키가 없었음:
```python
# 기존 반환값
return {
    "query": ..., "query_type": ..., "answer": ..., "citations": ...
}
# retrieved_docs는 LangGraph 내부 state에만 존재, 반환 안 됨
```

**해결**: `financial_graph.py`의 `run()` 반환 dict에 `"retrieved_docs": final["retrieved_docs"]` 추가.

---

### 문제 18 (버그): Google Gemini 임베딩 API 오류

**현상**: `answer_relevancy` 계산 시 404 에러:
```
models/text-embedding-004 is not found for API version v1beta
```

**근본 원인**:
`langchain_google_genai.GoogleGenerativeAIEmbeddings`가 v1beta API를 사용하는데,
`text-embedding-004`는 v1 API에서만 지원됨. 두 API 버전의 모델 지원 범위가 다름.

**해결**: Google 임베딩 사용 포기. VectorStoreManager와 동일한 `HuggingFaceEmbeddings("all-MiniLM-L6-v2")` 재사용.
- 장점: API 호출 비용/레이턴시 없음, 일관성 (검색-평가 동일 임베딩 공간)
- 단점: 영어 최적화 모델이므로 한국어 의미 유사도 품질이 다국어 모델 대비 낮을 수 있음

---

### 문제 19: `retrieved_docs`가 `(doc, score)` 튜플 — 타입 불일치

**현상**: contexts 추출 시 doc 객체를 직접 접근하려다 실패.

**근본 원인**: `VectorStoreManager.search()`가 `List[Tuple[DocumentChunk, float]]` 반환.
evaluator는 `DocumentChunk` 또는 `Document` 단독으로 가정.

**해결**:
```python
for item in raw_docs:
    doc = item[0] if isinstance(item, (tuple, list)) else item
    text = doc.content if hasattr(doc, "content") else doc.page_content
```

---

### 결정 20: 평가 데이터셋 설계 (20개 질문)

**문제**: 평가셋 ground truth를 어떻게 작성할 것인가.

**분석 및 트레이드오프**:
- **옵션 A**: 일반 지식 기반 정답 작성 — 빠르지만 실제 문서와 불일치 가능 → Context Recall 낮아짐
- **옵션 B**: 실제 파싱 결과에서 정답 추출 — 정확하지만 수동 작업 필요
- **옵션 C**: LLM으로 문서에서 Q&A 자동 생성 — 빠르지만 너무 쉬운 질문 생성 위험

**채택**: 옵션 A (빠른 MVP) + 단, Context Recall이 문서 내용 반영 여부를 간접적으로 측정함을 문서화.
실제 운영 단계에서는 실제 문서 청크에서 질문-정답 쌍 추출 필요 (옵션 B로 전환 권장).

**스모크 테스트 결과 (리스크 3문항)**:
```
Faithfulness    : 0.733  (LLM judge — 답변 신뢰도 양호)
Answer Relevancy: 0.562  (임베딩 유사도 — 보통, 영어 모델 한계)
Context Recall  : 0.167  (낮음 — ground truth가 문서 밖 키워드 포함 때문)
평균 Latency    : ~23초/질문 (Gemini API 포함)
```

---

---

## Phase 5 — FastAPI + Streamlit UI

### 결정 21: FastAPI 컴포넌트 싱글턴 — Lifespan 패턴

**문제**: FastAPI 요청마다 VectorStoreManager(HuggingFace 모델 로드 ~3초)를 초기화하면 레이턴시 폭증.

**채택한 해결책**: `@asynccontextmanager lifespan`으로 앱 시작 시 한 번만 `init_components()` 호출, 모듈 수준 전역 변수로 보관:
```python
_vsm: Optional[VectorStoreManager] = None
_agent: Optional[FinancialAgent] = None

@asynccontextmanager
async def lifespan(app):
    init_components()
    yield

app = FastAPI(lifespan=lifespan)
```
요청 핸들러에서는 `_require(component, name)` 헬퍼로 None 체크 후 사용.

---

### 결정 22: Streamlit @st.cache_resource로 동일 패턴 구현

**문제**: Streamlit은 매 상호작용마다 스크립트 전체를 재실행. 모델 로드가 반복됨.

**채택한 해결책**: `@st.cache_resource(show_spinner="모델 및 DB 로딩 중...")`로 컴포넌트 초기화 함수 데코레이팅. 세션 간 캐시 공유로 최초 1회만 로드.

---

### 문제 23 (버그): DARTFetcher 파라미터명 불일치

**현상**: `DARTFetcher(reports_dir=...)` 호출 시 `TypeError: unexpected keyword argument`.

**근본 원인**: `DARTFetcher.__init__` 파라미터가 `download_dir`인데, router/app.py에 `reports_dir=`로 작성.

**해결**: `download_dir=_REPORTS_DIR`로 수정. 동일하게 `report.local_path` → `report.file_path` (ReportMetadata 필드명 확인 후 수정).

---

### 결정 24: Streamlit에서 FastAPI 호출 방식 — 직접 Python 클래스 사용

**대안 비교**:
- **옵션 A (채택)**: Streamlit이 Python 클래스 직접 인스턴스화 (`@st.cache_resource`)
- **옵션 B**: Streamlit → FastAPI HTTP 호출 (httpx/requests)

**옵션 A 채택 이유**:
- 두 서버(uvicorn + streamlit) 동시 실행 불필요
- 네트워크 레이턴시 없음, 오류 처리 단순
- FastAPI는 외부 REST 클라이언트를 위한 별도 인터페이스로 유지

---

### 결정 25: 4개 REST 엔드포인트 설계

| 엔드포인트 | 설계 근거 |
|---|---|
| `POST /api/ingest` | 배경 처리 없이 동기식 — 수집 완료 후 응답 (청크 수 반환) |
| `POST /api/query` | LangGraph invoke가 동기이므로 async def + 블로킹 OK |
| `GET /api/companies` | ChromaDB `get(include=["metadatas"])`로 집계, 전체 스캔이지만 수백만 청크가 아니므로 허용 |
| `GET /api/health` | `bm25_docs` 길이로 인덱싱 상태 확인 (`vector_store._collection.count()` 대신 공개 API 사용) |