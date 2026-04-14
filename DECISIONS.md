# 기술 결정 & 문제 해결 로그

> 주요 설계 결정, 성능 튜닝, 문제 해결 과정을 추적하기 위한 문서입니다.

---

## 결정 1: DART 문서는 ZIP 내부 XML 기반 HTML로 파싱한다

문제:

- DART `document.zip` 응답 형식이 문서만 보고는 불명확했다.

결정:

- ZIP 내부 파일을 그대로 저장한 뒤 `lxml`로 XML 파싱한다.

결과:

- DART 고유 태그 구조를 보존한 채 SECTION / TABLE 기반 파싱이 가능해졌다.

---

## 결정 2: corp code는 정확 일치 우선, 필요 시 부분 일치와 alias를 사용한다

문제:

- 사용자는 "삼성전자", "네이버"처럼 입력하지만 DART 등록명은 더 길거나 영문일 수 있다.

결정:

- `corpCode.xml` 전체를 캐시하고
- 정확 일치 -> alias -> 부분 일치 순으로 corp code를 찾는다.

결과:

- `NAVER`, `HYBE` 같은 표기 차이를 흡수할 수 있게 됐다.

---

## 결정 3: DART XML은 `lxml XMLParser(recover=True)`로 파싱한다

문제:

- 실제 DART XML은 비표준 태그와 복구 가능한 XML 오류를 포함한다.

결정:

- `lxml.etree.XMLParser(recover=True, huge_tree=True)`를 사용한다.

결과:

- 대용량 사업보고서도 안정적으로 파싱할 수 있게 됐다.

---

## 결정 4: 섹션 경계는 `SECTION-1/2/3`과 `TITLE ATOC="Y"` 기준으로 잡는다

문제:

- 공시 문서의 논리 섹션 경계를 어디에 둘지 필요했다.

결정:

- `SECTION-1/2/3`를 순회하면서 직접 자식 `TITLE ATOC="Y"`를 읽어 섹션을 구성한다.

결과:

- DART 문서 구조와 거의 같은 단위로 파싱할 수 있게 됐다.

---

## 결정 5: 섹션 추출은 `id()` 기반 skip이 아니라 재귀 중단 방식으로 처리한다

문제:

- 초기 구현에서 lxml element proxy 특성 때문에 `id()` 기반 descendant skip이 실패했다.

결정:

- 하위 `SECTION-*`를 만나면 그 지점에서 재귀를 중단하도록 바꿨다.

결과:

- 섹션이 0개로 나오는 문제를 제거했다.

---

## 결정 6: 섹션 라벨은 rule-based keyword mapping으로 분류한다

문제:

- 공시 문서의 섹션 제목은 기업마다 표현이 달라 단순 exact match가 어렵다.

결정:

- 규칙 기반 키워드 매핑 테이블을 두고
- 명확하지 않은 경우에만 내용 기반 재분류를 사용한다.

결과:

- 사업개요, 리스크, 연구개발, 재무제표 등 주요 라벨을 안정적으로 분류할 수 있게 됐다.

---

## 결정 7: 청킹은 구조 우선, 문자 단위 재분할은 fallback으로만 사용한다

문제:

- 문서 전체를 바로 문자 단위 split하면 문단/표 경계를 잃고 너무 작은 청크가 많아진다.

결정:

- 먼저 구조 기반으로 블록을 묶고
- 단일 블록이 너무 길 때만 `RecursiveCharacterTextSplitter`를 적용한다.

결과:

- 문서 구조를 보존하면서도 과도한 fragmentation을 줄였다.

---

## 결정 8: 작은 표는 문단과 함께, 큰 표는 standalone 청크로 처리한다

문제:

- 모든 표를 독립 청크로 두면 참조 표가 지나치게 많아지고 의미가 잘게 끊긴다.

결정:

- threshold 미만 표는 인접 문단과 같이 누적하고
- 큰 표만 standalone 처리한다.

결과:

- 표 검색성과 문맥 보존의 균형을 잡을 수 있게 됐다.

---

## 결정 9: BM25는 한국어용 character bigram 토크나이저를 사용한다

문제:

- 공백 기반 토크나이징만으로는 조사 결합 표현을 잘 찾지 못한다.

결정:

- 한국어 질의/본문에는 character bigram 토크나이저를 사용한다.

결과:

- "매출액은", "영업이익이" 같은 표현에서도 lexical 검색 성능이 개선됐다.

---

## 결정 10: FastAPI와 Streamlit은 동일한 코어 컴포넌트를 공유한다

문제:

- 별도 코드 경로가 많아질수록 검증과 유지보수가 어려워진다.

결정:

- parser / vector store / agent 초기화 로직을 최대한 공통화한다.

결과:

- UI/API 동작 차이를 줄이고 수정 반영 범위를 좁힐 수 있게 됐다.

---

## 결정 11: single-company 정확도 개선은 retrieval 보강부터 처리한다

문제:

- 답변 오류의 상당수가 reasoning보다 retrieval contamination에서 시작됐다.

결정:

- 임베딩 교체, strict filter, `chunk_uid` dedup, rerank, evidence-first reasoning을 우선 도입한다.

결과:

- 단일 기업 질의의 오염도가 눈에 띄게 낮아졌다.

---

## 결정 12: 임베딩 기본값은 다국어 모델 `paraphrase-multilingual-MiniLM-L12-v2`를 사용한다

문제:

- 기존 영문 중심 임베딩은 한국어 공시 문서 retrieval에 한계가 있었다.

결정:

- 기본 임베딩을 multilingual sentence-transformers 모델로 교체한다.

결과:

- 한국어 질의와 한국어 공시 문서 사이 semantic match가 개선됐다.

---

## 결정 13: 컬렉션은 `dart_reports_v2`로 분리한다

문제:

- 임베딩 모델이 바뀐 상태에서 기존 인덱스와 혼용하면 검색 결과가 불안정해진다.

결정:

- Chroma 컬렉션을 `dart_reports_v2`로 분리하고 재인덱싱 기준을 명확히 한다.

결과:

- 새 retrieval 실험과 기존 인덱스를 혼동하지 않게 됐다.

---

## 결정 14: hybrid dedup과 RRF merge key는 raw text가 아니라 `chunk_uid`를 사용한다

문제:

- 서로 다른 기업/연도 문서라도 boilerplate 텍스트가 같으면 동일 청크처럼 합쳐질 수 있었다.

결정:

- parser에서 안정적인 `chunk_uid`를 부여하고 merge key로 사용한다.

결과:

- 반복 문구 때문에 출처가 섞이는 문제를 줄였다.

---

## 결정 15: strict metadata filter는 결과가 non-empty면 유지한다

문제:

- 기존 로직은 필터 결과가 1개면 오히려 필터를 버려 잘못된 청크가 다시 섞였다.

결정:

- filter 결과가 1개 이상이면 그대로 유지하고
- 0개일 때만 fallback한다.

결과:

- single-company wrong-document contamination을 구조적으로 줄였다.

---

## 결정 16: answer synthesis는 evidence-first로 구성한다

문제:

- retrieval 결과 전체를 바로 요약하면 약한 근거가 과잉 일반화될 수 있다.

결정:

- `retrieve -> evidence -> analyze -> cite` 흐름을 사용한다.

결과:

- 최종 답변과 근거의 연결이 더 명확해졌다.

---

## 결정 17: 평가 지표는 answer-only가 아니라 retrieval-aware로 확장한다

문제:

- faithfulness / relevancy만으로는 retrieval 실패와 synthesis 실패를 분리하기 어렵다.

결정:

- `retrieval_hit_at_k`, `section_match_rate`, `citation_coverage`를 추가한다.

결과:

- 검색 품질과 답변 품질을 나눠서 볼 수 있게 됐다.

---

## 결정 18: parent-child chunking을 도입한다

문제:

- 작은 청크는 검색에는 유리하지만 답변에 필요한 문맥이 부족했다.

결정:

- 검색은 자식 청크로 수행하고
- 같은 섹션 자식 청크를 묶은 부모 텍스트를 답변 컨텍스트로 사용한다.

결과:

- retrieval granularity와 reasoning context를 분리할 수 있게 됐다.

---

## 결정 19: contextual retrieval을 도입한다

문제:

- 일부 청크는 원문만으로는 문서 내 위치나 역할이 드러나지 않아 검색 매칭이 약했다.

결정:

- 자식 청크마다 LLM이 1문장 컨텍스트를 생성해 인덱싱 텍스트 앞에 prepend한다.

결과:

- BM25와 dense retrieval 모두에서 문맥 인지가 강화됐다.

---

## 결정 20: contextual ingest는 순차 호출 대신 `llm.batch()` 병렬 처리로 전환한다

문제:

- 문서 하나를 통으로 인덱싱할 때 청크 수만큼 LLM을 순차 호출해 시간이 지나치게 오래 걸렸다.

결정:

- `contextual_ingest()` 내부를 `llm.batch(..., config={"max_concurrency": ...})` 기반 병렬 처리로 전환한다.
- 병렬도는 `CONTEXTUAL_INGEST_MAX_WORKERS` 환경변수로 제어한다.
- app/API는 같은 설정을 사용한다.

결과:

- 순차 처리 대비 contextual ingest의 체감 속도가 크게 개선됐다.

---

## 결정 21: larger chunk 실험은 moderate tuning으로 제한한다

문제:

- LLM 성능과 context window가 좋아진 만큼 청크 수를 줄여 ingest 시간을 단축할 여지가 있었다.

결정:

- chunking 알고리즘 자체를 바꾸지 않고
- moderate chunk size expansion만 시험한다.

실험 결과:

| 설정 | 청크 수 | contextual ingest | 판단 |
|---|---:|---:|---|
| `1500 / 200` | `502` | `1013.569초` | 기준선 |
| `2800 / 350` | `266` | `292.289초` | 속도 우수, 리스크 질의 품질 회귀 |
| `2500 / 320` | `300` | `584.25초` | 최종 채택 |

결과:

- 너무 큰 청크는 검색 품질을 해칠 수 있다는 점을 확인했다.
- `2500 / 320`이 속도와 품질의 균형이 가장 좋았다.

---

## 결정 22: 파서 기본 청크 설정은 `2500 / 320`으로 올린다

문제:

- `1500 / 200` 기준은 정확도는 괜찮았지만 contextual ingest LLM 호출 수가 너무 많았다.

결정:

- `FinancialParser` 기본값을 `chunk_size=2500`, `chunk_overlap=320`으로 변경한다.
- app/API도 같은 기본값을 사용하도록 맞춘다.

결과:

- 자식 청크 수가 줄어들고 ingest 시간이 유의미하게 감소했다.

---

## 결정 23: larger chunk에서도 retrieval 신호를 보강하기 위해 deterministic metadata prefix를 추가한다

문제:

- 청크가 커질수록 섹션/문서 정체성이 본문 속에 묻혀 특정 질의에서 retrieval 품질이 흔들릴 수 있었다.

결정:

- contextual ingest 시 생성되는 인덱싱 텍스트 앞에 다음 메타데이터 라인을 추가한다.
  - 회사 / 연도 / 보고서
  - 섹션 breadcrumb
  - section label / block type

결과:

- 큰 청크에서도 회사/연도/섹션 신호가 검색 입력에 명시적으로 남게 됐다.

---

## 결정 24: `2800 / 350`은 채택하지 않는다

문제:

- `2800 / 350`은 ingest 속도는 좋았지만 리스크 질의에서 관련 섹션이 약해지고 답변 품질이 불안정했다.

결정:

- 속도만으로 채택하지 않고 품질 회귀가 없는 `2500 / 320`을 최종안으로 선택한다.

결과:

- 사업 질의와 리스크 질의 모두 smoke 수준에서 다시 안정화됐다.

---

## 현재 운영 메모

- Python 3.14 환경에서 `langchain_core`의 Pydantic v1 경고가 남아 있다.
- `langchain_community.vectorstores.Chroma` deprecation 경고가 남아 있다.
- Hugging Face 모델 캐시 `.hf_cache/`가 로컬에 생성된다.

---

## 다음 검토 포인트

- contextual ingest 결과를 `chunk_uid` 기준으로 캐시할지
- `table_context` 이름을 preview 의미로 바꿀지
- larger chunk 설정이 multi-company 질의에서도 안정적인지
- parent chunk 길이 `6000`이 최적값인지
