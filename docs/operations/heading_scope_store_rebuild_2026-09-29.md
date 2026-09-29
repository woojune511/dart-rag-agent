# 11개 2023 보고서 저장소 재구축

2026-09-29. **COMPLETE_READY**. 사용자가 확정한 11개 회사의 2023 사업보고서를
새 파서로 재처리해 별도 Chroma 저장소를 만들었다. 기존 NAVER 2022·2023 저장소와
앱 `.env`는 변경하지 않았다. 답변 생성·정답률 평가·앱 연결 전환은 실행하지 않았다.

## 생성한 저장소

- 경로: `data/app_full11_2023_20260929`
- Collection: `dart_reports_v3_full11_2023`
- Parser: `financial_parser_v3_heading_scope`
- Profile: `structural_selective_v2_prefix_2500_320`, chunk 2500/320
- Embedding: `text-embedding-3-large`, 3072차원; HNSW 거리 l2
- Readiness: **compatible**
- 11개 원본, 473개 절/parent, 14,005개 청크·벡터, 12,330개 table payload

## 재사용과 추가 호출

| 회사 | 새 청크 | 기존 벡터 재사용 | 새 벡터가 필요한 청크 |
| --- | ---: | ---: | ---: |
| KB금융 | 2,407 | 1,316 | 1,091 |
| POSCO홀딩스 | 1,739 | 1,257 | 482 |
| SK하이닉스 | 974 | 702 | 272 |
| NAVER | 1,124 | 958 | 166 |
| 삼성전자 | 1,001 | 742 | 259 |
| 셀트리온 | 1,131 | 948 | 183 |
| 카카오 | 1,358 | 1,215 | 143 |
| 현대자동차 | 1,017 | 796 | 221 |
| LG에너지솔루션 | 804 | 731 | 73 |
| SK이노베이션 | 1,965 | 1,330 | 635 |
| 카카오뱅크 | 485 | 264 | 221 |
| 합계 | **14,005** | **10,259** | **3,746** |

원본 HTML을 재파싱해 metadata·parents를 새로 만들었다. full77 table corpus와
벡터 파일의 저장된 hash, 벡터 차원·유한값·비영 벡터를 검사하고, 같은 filing의
**전체 embedding 입력이 정확히 같은 경우에만** 이전 벡터를 재사용했다.
청크 ID나 원문 숫자만 같다는 이유로 재사용하지 않았다. 새 embedding 입력은
텍스트 hash로 중복 제거해 **3,658개**다.

- 실제 embedding 호출: **58회**, 입력 **2,866,885 tokens**
- 추정 비용: **USD0.37269505**, 미결 예약 0, 오류·재시도 0
- 사전 전체 예약: USD0.37366017, 작업 상한 USD2
- Embedding 단계 237.67초, 저장·readback 단계 176.82초; 준비·테스트 시간 별도
- 답변·query embedding·judge·문서 수집 호출: 0

비용은 2026-09-29 확인한 [공식 embedding 요율](https://developers.openai.com/api/docs/models/text-embedding-3-large)
(100만 input tokens당 USD0.13)과 실제 응답 usage로 계산한 추정치이며 청구서가 아니다.
이전 실험 예산은 재사용하지 않았다. 사용자의 이번 재구축 지시에 따라 실행했고,
USD2는 에이전트가 정한 작업 상한이다.

## 실행 전 해결한 파싱 지연

전체 문서에서는 이전 실험에 기록된 `_INLINE_BODY_SEPARATOR_RE`의 중복 분할
탐색이 남아 있었다. 콜론 없는 짧은 음성 예제도 별도 프로세스에서 2초 제한을
넘어 종료됐다. `(?:\s*[A-Za-z가-힣&]+)*`를 공백이 있는 단어 사이 반복으로
바꿨다. 공백 없는 연속 문자 그룹은 앞 그룹에 합쳐지므로 매칭 언어를 유지한다.
이번에는 실험 전용 monkeypatch가 아니라 제품 parser의 정규식을 수정했다.

신규 테스트는 짧은 조합의 전체 match span·capture를 이전 패턴과 대조하고,
100,003자 콜론 없는 문자열을 제한된 subprocess에서 검사한다. 기존 제목 범위
테스트와 포함해 전체 **2,141/2,141 통과 (52.876초)**. 추가 successor/regex focused
14개도 통과했다. 전체 473개 절은 timeout fallback 없이 파싱했다
(`section_parse_budget_sec=0`인 명시적 rebuild 설정; 앱의 시간 제한과 동일하다는 뜻은 아님).

## 저장 검증

1. 실제 임시 Chroma에서 두 합성 filing의 병합·readback·manifest-last 계약 확인.
2. 58개 전체 요청의 text hash·token 수·8192 한도·합산 비용 상한을 사전 확인.
   실제 SDK 모의 호출은 첫/마지막 대표 배치 2개이며, 전체 58회 모의 호출로 세지 않는다.
3. 새 graph·table payload·parents와 Chroma를 저장하고 닫은 후 재개방.
   14,005개 전체 ID·텍스트·metadata·float32 벡터를 기대값 hash와 대조했다.
4. graph·payload·parent 파일을 원래 기대 객체와 비교했다.
5. 보고서별 scope를 적용한 dense self-vector probe 11개와 BM25 smoke 11개 통과.
   이는 검색 경로·scope의 동작 검사이며 질문에 대한 정답 근거 회수율이 아니다.
6. 저장된 KB금융 등급 표와 삼성전자 신용평가 설명에서 이전 자회사·부문 제목이
   사라지고 올바른 새 항목 제목이 남는 것을 확인했다.
7. 187개 보호 입력(원본, 기존 table corpus/vector, 당시 source, 활성 NAVER store,
   `.env` 등)의 hash가 동일함을 확인했다. 새 manifest는 검증 뒤 마지막에 발행했다.

준비 과정의 인코딩 별칭 오타는 API 호출 전에 수정했다. 최초 전체 SDK 모의 실행은
JSON streaming 저장 지연으로 중단하고 로그를 보존했다. JSON을 한 번에 직렬화하도록
정리한 후 전체 입력 검사와 대표 SDK mock을 완료했다. 두 준비 이슈는 실제 provider
오류·재시도에 포함하지 않으며, 유료 실행은 한 번만 수행했다.

## 연결과 산출물

앱 연결에 사용할 값은 다음과 같다. 현재 `.env`에는 적용하지 않았다.

```dotenv
DART_STORE_PATH=C:/Users/geonj/Desktop/dart-rag-agent/data/app_full11_2023_20260929
DART_COLLECTION_NAME=dart_reports_v3_full11_2023
```

현재 앱의 기존 NAVER v2 store는 새 v3 parser와 mismatch다. 새 저장소는 지정한
collection과 manifest 기준으로 준비됐지만, 앱 설정을 전환·재시작한 실동작이나
LLM 답변 개선을 검증한 것은 아니다.

로컬 실행 기록: `benchmarks/results/heading_scope_store_rebuild_2026-09-29/`.
`preparation.json`, `admission.json`, 사용 완료 marker, mock/live usage와 budget,
`build_result.json`, `stored_record_hashes.json`, `retrieval_smoke.json`, 전체 테스트와
20초 heartbeat, 연결용 `app_settings.env`를 보존한다.
대용량 재파싱 corpus·재사용 벡터·원시 embedding 요청/응답은
`D:/CodexArtifacts/dart-rag-agent/heading_scope_store_rebuild_2026-09-29/`에 있다.
원본 실험과 신규 결과를 구분하며 자동 resume·재실행·설정 전환은 없다.
